"""
Backfill every granular row type from Claude Code's local session logs.

Scans every `~/.claude/projects/*/*.jsonl` (and also `~/.claude/sessions/*.jsonl`
if present) and emits rows into six tables:

    turns         ← assistant messages (w/ content stats + thinking/text/tool
                    block counts + stop_reason + iterations + web_search/fetch)
    tool_calls    ← one per `tool_use` block inside each assistant turn
    tool_results  ← one per `tool_result` block inside user turns
    user_prompts  ← one per `user` event (real prompt or tool_result wrapper)
    events        ← everything else: system, permission-mode, attachment,
                    file-history-snapshot, queue-operation, last-prompt
                    (system.turn_duration duration_ms is hoisted to a column)

All inserts are idempotent via UNIQUE keys. Re-running is safe and is the
expected way to catch up incrementally (use --since).

After the row-level pass, a post-pass joins `system.turn_duration` events to
their parent turns and fills `turns.duration_ms`.

Usage:
    python claude_usage_backfill.py                # full rescan
    python claude_usage_backfill.py --since 6h     # only files touched in last 6h
    python claude_usage_backfill.py --stats        # print DB stats after
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Sibling import — see claude_code_usage.py for rationale.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_usage_db as dbmod  # noqa: E402

# Per-account glob sets.  Each account's JSONL files live under its own
# CLAUDE_CONFIG_DIR — primary at ~/.claude, overflow at ~/.claude-alt.
ACCOUNT_GLOBS = {
    "primary": [
        os.path.expanduser("~/.claude/projects/*/*.jsonl"),
        os.path.expanduser("~/.claude/sessions/*.jsonl"),
    ],
    "overflow": [
        os.path.expanduser("~/.claude-alt/projects/*/*.jsonl"),
        os.path.expanduser("~/.claude-alt/sessions/*.jsonl"),
    ],
}

# Trim tool_use input payloads to this size before storing. Keeps DB small
# while still preserving enough to answer "what did I Grep for most often"
# type queries. `input_bytes` still records the full pre-trim size.
MAX_INPUT_JSON_BYTES = 4096


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _parse_since(arg):
    """Parse '6h', '3d', '30m' → seconds."""
    if not arg:
        return None
    m = re.match(r"^(\d+)([hdm])$", arg.strip())
    if not m:
        raise ValueError(f"--since must be like 6h, 3d, 30m; got {arg!r}")
    n, unit = int(m.group(1)), m.group(2)
    return n * {"h": 3600, "d": 86400, "m": 60}[unit]


def _files_to_scan(since_seconds):
    """Return list of (path, account) tuples across all configured accounts."""
    results = []
    for account, globs in ACCOUNT_GLOBS.items():
        for pattern in globs:
            for f in sorted(glob.glob(pattern)):
                results.append((f, account))
    if since_seconds is None:
        return results
    cutoff = time.time() - since_seconds
    return [(f, acct) for f, acct in results if os.path.getmtime(f) >= cutoff]


def _content_stats(blocks):
    """Walk a message.content list, tally per-block-type stats.

    Returns a dict with:
      num_thinking, thinking_chars, num_text, text_chars, num_tool_uses,
      tool_use_blocks (list of dicts ready to become tool_calls rows)
    """
    out = {
        "num_thinking": 0, "thinking_chars": 0,
        "num_text": 0, "text_chars": 0,
        "num_tool_uses": 0,
        "tool_use_blocks": [],
    }
    if not isinstance(blocks, list):
        return out
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "thinking":
            out["num_thinking"] += 1
            out["thinking_chars"] += len(b.get("thinking") or "")
        elif t == "text":
            out["num_text"] += 1
            out["text_chars"] += len(b.get("text") or "")
        elif t == "tool_use":
            out["num_tool_uses"] += 1
            out["tool_use_blocks"].append(b)
    return out


def _user_content_stats(blocks):
    """Walk a user.message.content list, tally text/image/tool_result blocks."""
    out = {
        "text_chars": 0,
        "image_count": 0,
        "tool_result_count": 0,
        "tool_result_blocks": [],
        "text_preview": "",
    }
    # content may be a plain string in some older sessions
    if isinstance(blocks, str):
        out["text_chars"] = len(blocks)
        out["text_preview"] = blocks[:200]
        return out
    if not isinstance(blocks, list):
        return out
    text_parts = []
    for b in blocks:
        if isinstance(b, str):
            out["text_chars"] += len(b)
            text_parts.append(b)
            continue
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            txt = b.get("text") or ""
            out["text_chars"] += len(txt)
            text_parts.append(txt)
        elif t == "image":
            out["image_count"] += 1
        elif t == "tool_result":
            out["tool_result_count"] += 1
            out["tool_result_blocks"].append(b)
    joined = " ".join(text_parts).strip()
    out["text_preview"] = joined[:200]
    return out


def _int_or_zero(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


# ------------------------------------------------------------------
# per-entry extractors — each returns a list of (table, row) inserts
# ------------------------------------------------------------------

def _extract_assistant(entry, source_file, account="primary"):
    """Return list of (table, row) pairs for one assistant entry."""
    msg = entry.get("message") or {}
    usage = msg.get("usage") or {}
    message_uuid = entry.get("uuid")
    if not message_uuid or "output_tokens" not in usage:
        return []

    stats = _content_stats(msg.get("content"))
    cache_creation = usage.get("cache_creation") or {}
    server_tool = usage.get("server_tool_use") or {}
    iterations = usage.get("iterations")
    iterations_count = len(iterations) if isinstance(iterations, list) else None

    rows = []

    turn = {
        "message_uuid":                message_uuid,
        "message_id":                  msg.get("id"),
        "request_id":                  entry.get("requestId"),
        "session_id":                  entry.get("sessionId") or "",
        "parent_uuid":                 entry.get("parentUuid"),
        "ts":                          entry.get("timestamp"),
        "project_cwd":                 entry.get("cwd"),
        "git_branch":                  entry.get("gitBranch"),
        "model":                       msg.get("model"),
        "input_tokens":                _int_or_zero(usage.get("input_tokens")),
        "output_tokens":               _int_or_zero(usage.get("output_tokens")),
        "cache_creation_input_tokens": _int_or_zero(usage.get("cache_creation_input_tokens")),
        "cache_read_input_tokens":     _int_or_zero(usage.get("cache_read_input_tokens")),
        "ephemeral_1h_input_tokens":   _int_or_zero(cache_creation.get("ephemeral_1h_input_tokens")),
        "ephemeral_5m_input_tokens":   _int_or_zero(cache_creation.get("ephemeral_5m_input_tokens")),
        "service_tier":                usage.get("service_tier"),
        "is_sidechain":                1 if entry.get("isSidechain") else 0,
        "cc_version":                  entry.get("version"),
        "source_file":                 source_file,
        "account":                     account,
        # new granular columns
        "stop_reason":                 msg.get("stop_reason"),
        "stop_details":                json.dumps(msg.get("stop_details")) if msg.get("stop_details") else None,
        "num_thinking_blocks":         stats["num_thinking"],
        "thinking_chars":              stats["thinking_chars"],
        "num_text_blocks":             stats["num_text"],
        "text_chars":                  stats["text_chars"],
        "num_tool_uses":               stats["num_tool_uses"],
        "permission_mode":             entry.get("permissionMode"),
        "is_api_error":                1 if entry.get("isApiErrorMessage") else 0,
        "is_compact_summary":          1 if entry.get("isCompactSummary") else 0,
        "is_meta":                     1 if entry.get("isMeta") else 0,
        "iterations_count":            iterations_count,
        "web_search_requests":         _int_or_zero(server_tool.get("web_search_requests")),
        "web_fetch_requests":          _int_or_zero(server_tool.get("web_fetch_requests")),
        "entrypoint":                  entry.get("entrypoint"),
        "prompt_id":                   entry.get("promptId"),
        "user_type":                   entry.get("userType"),
        "duration_ms":                 None,  # filled in post-pass from system.turn_duration
    }
    rows.append(("turns", turn))

    # tool_calls rows — one per tool_use block
    for b in stats["tool_use_blocks"]:
        tool_use_id = b.get("id")
        if not tool_use_id:
            continue
        input_payload = b.get("input")
        try:
            input_json = json.dumps(input_payload, default=str)
        except (TypeError, ValueError):
            input_json = str(input_payload)
        input_bytes = len(input_json.encode("utf-8"))
        if input_bytes > MAX_INPUT_JSON_BYTES:
            input_json = input_json[:MAX_INPUT_JSON_BYTES]
        rows.append(("tool_calls", {
            "tool_use_id":  tool_use_id,
            "message_uuid": message_uuid,
            "session_id":   entry.get("sessionId"),
            "ts":           entry.get("timestamp"),
            "project_cwd":  entry.get("cwd"),
            "tool_name":    b.get("name") or "?",
            "input_json":   input_json,
            "input_bytes":  input_bytes,
            "is_sidechain": 1 if entry.get("isSidechain") else 0,
            "model":        msg.get("model"),
        }))
    return rows


def _extract_user(entry, source_file):
    """Return list of (table, row) pairs for one user entry."""
    msg = entry.get("message") or {}
    message_uuid = entry.get("uuid")
    if not message_uuid:
        return []

    stats = _user_content_stats(msg.get("content"))
    is_real_prompt = 1 if (stats["tool_result_count"] == 0 and stats["text_chars"] > 0) else 0

    rows = [("user_prompts", {
        "message_uuid":      message_uuid,
        "session_id":        entry.get("sessionId"),
        "parent_uuid":       entry.get("parentUuid"),
        "prompt_id":         entry.get("promptId"),
        "ts":                entry.get("timestamp"),
        "project_cwd":       entry.get("cwd"),
        "text_chars":        stats["text_chars"],
        "image_count":       stats["image_count"],
        "tool_result_count": stats["tool_result_count"],
        "is_real_prompt":    is_real_prompt,
        "is_sidechain":      1 if entry.get("isSidechain") else 0,
        "user_type":         entry.get("userType"),
        "text_preview":      stats["text_preview"] or None,
    })]

    # tool_results rows — one per tool_result block
    tur = entry.get("toolUseResult") or {}
    success_flag = None
    command_name = None
    if isinstance(tur, dict):
        if "success" in tur:
            success_flag = 1 if tur.get("success") else 0
        command_name = tur.get("commandName")

    for b in stats["tool_result_blocks"]:
        tool_use_id = b.get("tool_use_id")
        if not tool_use_id:
            continue
        content = b.get("content")
        if isinstance(content, str):
            result_bytes = len(content.encode("utf-8"))
        else:
            try:
                result_bytes = len(json.dumps(content, default=str).encode("utf-8"))
            except (TypeError, ValueError):
                result_bytes = None
        rows.append(("tool_results", {
            "tool_use_id":          tool_use_id,
            "wrapper_message_uuid": message_uuid,
            "session_id":           entry.get("sessionId"),
            "ts":                   entry.get("timestamp"),
            "is_error":             1 if b.get("is_error") else 0,
            "success":              success_flag,
            "result_bytes":         result_bytes,
            "command_name":         command_name,
        }))
    return rows


def _extract_event(entry, source_file):
    """Catchall: system, permission-mode, attachment, file-history-snapshot,
    queue-operation, last-prompt, etc."""
    t = entry.get("type")
    subtype = entry.get("subtype")
    # Hoist duration_ms for system.turn_duration specifically
    duration_ms = entry.get("durationMs")
    try:
        payload = json.dumps(entry, default=str)
    except (TypeError, ValueError):
        payload = None
    return [("events", {
        "event_uuid":   entry.get("uuid"),
        "type":         t,
        "subtype":      subtype,
        "session_id":   entry.get("sessionId"),
        "parent_uuid":  entry.get("parentUuid"),
        "ts":           entry.get("timestamp"),
        "project_cwd":  entry.get("cwd"),
        "duration_ms":  duration_ms,
        "payload_json": payload,
        "source_file":  source_file,
    })]


def _dispatch(entry, source_file, account="primary"):
    t = entry.get("type")
    if t == "assistant":
        return _extract_assistant(entry, source_file, account=account)
    if t == "user":
        return _extract_user(entry, source_file)
    return _extract_event(entry, source_file)


# ------------------------------------------------------------------
# main backfill loop
# ------------------------------------------------------------------

def backfill(since=None, verbose=True):
    conn = dbmod.connect()
    files = _files_to_scan(since)
    counts = {
        "entries": 0,
        "turns": 0, "tool_calls": 0, "tool_results": 0,
        "user_prompts": 0, "events": 0,
    }
    inserted = {k: 0 for k in counts if k != "entries"}

    if verbose:
        print(f"scanning {len(files)} jsonl files…")

    inserters = {
        "turns":         dbmod.upsert_turn,
        "tool_calls":    dbmod.upsert_tool_call,
        "tool_results":  dbmod.upsert_tool_result,
        "user_prompts":  dbmod.upsert_user_prompt,
        "events":        dbmod.upsert_event,
    }

    # Batch in explicit transactions of ~2000 rows each. Keeps the write
    # lock held for short bursts so the widget / launchd snapshot can
    # interleave reads between batches without waiting minutes.
    BATCH_ROWS = 2000
    rows_in_txn = 0
    conn.execute("BEGIN")

    for i, (path, account) in enumerate(files, 1):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    counts["entries"] += 1
                    rows = _dispatch(entry, path, account=account)
                    for table, row in rows:
                        counts[table] += 1
                        before = conn.total_changes
                        inserters[table](conn, row)
                        if conn.total_changes > before:
                            inserted[table] += 1
                        rows_in_txn += 1
                        if rows_in_txn >= BATCH_ROWS:
                            conn.execute("COMMIT")
                            conn.execute("BEGIN")
                            rows_in_txn = 0
        except Exception as e:
            if verbose:
                print(f"  skip {path}: {e}")
            continue
        if verbose and i % 50 == 0:
            print(f"  [{i}/{len(files)}] scanned")

    conn.execute("COMMIT")

    # Post-pass: fill turns.duration_ms from system.turn_duration events.
    #
    # Performance: naively this UPDATE has a `WHERE duration_ms IS NULL`
    # and runs the correlated subquery against every such row in the
    # table. On a DB with months of history and tens of thousands of
    # historical turns that never matched a duration event (older CC
    # versions didn't emit them), that's an O(N) subquery-per-row scan
    # that spins at 100% CPU for minutes on a `--since 10m` incremental
    # backfill — which is absurd since those 10 minutes of new rows are
    # all we're trying to join. Scope the UPDATE to the same time window
    # we just ingested so the join only runs against rows that could
    # plausibly have new matching events.
    if verbose:
        print("post-pass: joining system.turn_duration → turns.duration_ms …")
    if since is not None:
        since_iso = (
            datetime.fromtimestamp(time.time() - since, tz=timezone.utc).isoformat()
        )
        update_sql = """
            UPDATE turns
               SET duration_ms = (
                   SELECT e.duration_ms
                     FROM events e
                    WHERE e.type = 'system'
                      AND e.subtype = 'turn_duration'
                      AND e.parent_uuid = turns.message_uuid
                    ORDER BY e.ts ASC
                    LIMIT 1
               )
             WHERE duration_ms IS NULL
               AND ts >= ?
        """
        updated = conn.execute(update_sql, (since_iso,)).rowcount
    else:
        # Full scan (no --since): accept the long post-pass. Users who run
        # an unbounded rescan already expect it to take minutes.
        updated = conn.execute(
            """
            UPDATE turns
               SET duration_ms = (
                   SELECT e.duration_ms
                     FROM events e
                    WHERE e.type = 'system'
                      AND e.subtype = 'turn_duration'
                      AND e.parent_uuid = turns.message_uuid
                    ORDER BY e.ts ASC
                    LIMIT 1
               )
             WHERE duration_ms IS NULL
            """
        ).rowcount
    conn.commit()

    if verbose:
        print(
            f"done. {counts['entries']} entries scanned.\n"
            f"  turns: seen {counts['turns']} / new {inserted['turns']}\n"
            f"  tool_calls: seen {counts['tool_calls']} / new {inserted['tool_calls']}\n"
            f"  tool_results: seen {counts['tool_results']} / new {inserted['tool_results']}\n"
            f"  user_prompts: seen {counts['user_prompts']} / new {inserted['user_prompts']}\n"
            f"  events: seen {counts['events']} / new {inserted['events']}\n"
            f"  turns.duration_ms filled in post-pass: {updated}"
        )
    return {"counts": counts, "inserted": inserted, "files": len(files)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="only scan files modified within this window, e.g. 6h / 3d / 30m")
    ap.add_argument("--stats", action="store_true", help="print DB stats after backfill")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    since_seconds = _parse_since(args.since) if args.since else None
    backfill(since=since_seconds, verbose=not args.quiet)

    if args.stats:
        conn = dbmod.connect()
        s = dbmod.stats(conn)
        print()
        print("DB stats:")
        for k, v in s.items():
            print(f"  {k:20s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
