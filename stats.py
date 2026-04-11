"""
cc-usage stats — the fun report.

One command, one big answer: every behavioral stat we can pull out of the
granular DB. Runs against the sibling claude_usage.db populated by
claude_usage_backfill.py.

Usage:
    python stats.py              # full report to stdout
    python stats.py --days 7     # window to last N days (default 30)
    python stats.py --today      # just today
    python stats.py --project my-repo   # filter everything by project substring

Sections:
  1. Overview — row counts + date range
  2. Token burn — by day, by model, cache hit rate
  3. Projects — top by tokens, turns, tool calls, avg turns/session
  4. Tools — the whole inventory: which tools, how often, error rates
  5. Tool-specific — top Bash commands, top Grep patterns, Read hot files
  6. Turn behavior — stop_reason distribution, iterations, duration stats
  7. Thinking vs visible — how much output is reasoning vs text
  8. User activity — prompts per day, text length, screenshot pastes
  9. Sessions — length distribution, turns per session, longest
 10. Hourly heatmap — turns by hour-of-day
 11. Errors — api errors, tool result errors
 12. Permission modes — plan / accept_edits / default distribution
 13. Sidechain tax — token share of subagent turns
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_usage_db as dbmod  # noqa: E402

# Local wall-clock timezone for human-friendly displays. Override with
# CC_USAGE_TZ env var (any IANA zone name). Defaults to America/Los_Angeles
# to match the Anthropic quota reset convention.
PT = ZoneInfo(os.environ.get("CC_USAGE_TZ", "America/Los_Angeles"))


# ------------------------------------------------------------------
# rendering helpers
# ------------------------------------------------------------------

def h1(s):   print(f"\n{'═' * 78}\n  {s}\n{'═' * 78}")
def h2(s):   print(f"\n── {s} ──")
def row(*cells, widths=None):
    widths = widths or [20] * len(cells)
    print("  " + "  ".join(str(c).ljust(w) for c, w in zip(cells, widths)))


def fmt_n(n):
    if n is None:        return "—"
    if n >= 1_000_000:   return f"{n/1_000_000:.1f}M"
    if n >= 1_000:       return f"{n/1_000:.1f}k"
    return str(int(n))


def fmt_ms(ms):
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{int(ms)}ms"
    if ms < 60_000:
        return f"{ms/1000:.1f}s"
    return f"{ms/60_000:.1f}m"


def bar(val, maxv, width=24):
    if not maxv:
        return ""
    filled = int(round(width * val / maxv))
    return "█" * filled + "░" * (width - filled)


def trim(s, n):
    if s is None: return ""
    return s if len(s) <= n else s[:n-1] + "…"


def short_model(m):
    if not m:           return "?"
    if "opus" in m:     return "opus"
    if "sonnet" in m:   return "sonnet"
    if "haiku" in m:    return "haiku"
    return m[:10]


def short_project(p):
    if not p:           return "?"
    return Path(p).name


# ------------------------------------------------------------------
# time window
# ------------------------------------------------------------------

def build_window(args):
    now_utc = datetime.now(timezone.utc)
    if args.today:
        start_pt = datetime.now(PT).replace(hour=0, minute=0, second=0, microsecond=0)
        since = start_pt.astimezone(timezone.utc)
        label = "today (PT)"
    else:
        since = now_utc - timedelta(days=args.days)
        label = f"last {args.days}d"
    return since.isoformat(), label


# ------------------------------------------------------------------
# sections
# ------------------------------------------------------------------

def section_overview(conn, since_iso, label):
    h1(f"cc-usage stats · window: {label}")
    s = dbmod.stats(conn)
    row("snapshots",    fmt_n(s['snapshots']))
    row("turns",        fmt_n(s['turns']))
    row("tool_calls",   fmt_n(s['tool_calls']))
    row("tool_results", fmt_n(s['tool_results']))
    row("user_prompts", fmt_n(s['user_prompts']))
    row("events",       fmt_n(s['events']))
    row("sessions",     fmt_n(s['sessions']))
    row("projects",     fmt_n(s['projects']))
    row("earliest",     s['earliest_turn'] or "—")
    row("latest",       s['latest_turn'] or "—")


def section_token_burn(conn, since_iso, project):
    h1("Token burn — daily + by model")
    where, params = _where(since_iso, project)
    rows = conn.execute(f"""
        SELECT substr(ts, 1, 10) AS day,
               SUM(input_tokens)                 AS in_tok,
               SUM(output_tokens)                AS out_tok,
               SUM(cache_read_input_tokens)      AS cache_r,
               SUM(cache_creation_input_tokens)  AS cache_c,
               COUNT(*)                          AS turns
          FROM turns
         WHERE {where}
         GROUP BY day
         ORDER BY day DESC
         LIMIT 30
    """, params).fetchall()

    h2("Daily totals")
    maxv = max((r["out_tok"] or 0) for r in rows) if rows else 0
    widths = [10, 7, 9, 9, 9, 9, 26]
    row("day", "turns", "in", "out", "cache_r", "cache_c", "out graph", widths=widths)
    for r in rows:
        row(r["day"], fmt_n(r["turns"]), fmt_n(r["in_tok"]), fmt_n(r["out_tok"]),
            fmt_n(r["cache_r"]), fmt_n(r["cache_c"]),
            bar(r["out_tok"] or 0, maxv),
            widths=widths)

    h2("By model")
    rows = conn.execute(f"""
        SELECT model,
               COUNT(*)                          AS turns,
               SUM(input_tokens)                 AS in_tok,
               SUM(output_tokens)                AS out_tok,
               SUM(cache_read_input_tokens)      AS cache_r,
               SUM(cache_creation_input_tokens)  AS cache_c
          FROM turns
         WHERE {where}
         GROUP BY model
         ORDER BY out_tok DESC
    """, params).fetchall()
    widths = [14, 8, 10, 10, 10, 10, 10]
    row("model", "turns", "in", "out", "cache_r", "cache_c", "cache_hit", widths=widths)
    for r in rows:
        total_in = (r["in_tok"] or 0) + (r["cache_r"] or 0) + (r["cache_c"] or 0)
        hit = (r["cache_r"] or 0) / total_in * 100 if total_in else 0
        row(short_model(r["model"]), fmt_n(r["turns"]),
            fmt_n(r["in_tok"]), fmt_n(r["out_tok"]),
            fmt_n(r["cache_r"]), fmt_n(r["cache_c"]),
            f"{hit:.1f}%",
            widths=widths)


def section_projects(conn, since_iso, project):
    h1("Projects — top by output tokens")
    where, params = _where(since_iso, project)
    rows = conn.execute(f"""
        SELECT project_cwd,
               COUNT(*)             AS turns,
               SUM(output_tokens)   AS out_tok,
               SUM(input_tokens + cache_read_input_tokens + cache_creation_input_tokens) AS in_total,
               COUNT(DISTINCT session_id) AS sessions,
               SUM(num_tool_uses)   AS tools
          FROM turns
         WHERE {where}
         GROUP BY project_cwd
         ORDER BY out_tok DESC
         LIMIT 20
    """, params).fetchall()
    maxv = max((r["out_tok"] or 0) for r in rows) if rows else 0
    widths = [22, 7, 9, 9, 8, 8, 24]
    row("project", "turns", "out_tok", "in_tok", "sess", "tools", "share", widths=widths)
    for r in rows:
        row(short_project(r["project_cwd"]),
            fmt_n(r["turns"]), fmt_n(r["out_tok"]),
            fmt_n(r["in_total"]),
            r["sessions"], fmt_n(r["tools"]),
            bar(r["out_tok"] or 0, maxv),
            widths=widths)


def section_tools(conn, since_iso, project):
    h1("Tools — inventory")
    where, params = _where(since_iso, project, table="tool_calls")
    rows = conn.execute(f"""
        SELECT tool_name, COUNT(*) AS n,
               SUM(input_bytes) AS total_bytes,
               AVG(input_bytes) AS avg_bytes
          FROM tool_calls
         WHERE {where}
         GROUP BY tool_name
         ORDER BY n DESC
    """, params).fetchall()
    maxv = rows[0]["n"] if rows else 0
    total = sum(r["n"] for r in rows) or 1
    widths = [20, 8, 7, 11, 10, 22]
    row("tool", "count", "share", "total_in", "avg_in", "", widths=widths)
    for r in rows:
        row(r["tool_name"], fmt_n(r["n"]), f"{r['n']/total*100:.1f}%",
            fmt_n(r["total_bytes"]), fmt_n(r["avg_bytes"]),
            bar(r["n"], maxv),
            widths=widths)

    # Per-project tool breakdown — what's my default tool in each project
    h2("Most-used tool per project")
    per_proj = conn.execute(f"""
        SELECT project_cwd, tool_name, COUNT(*) AS n
          FROM tool_calls
         WHERE {where}
         GROUP BY project_cwd, tool_name
    """, params).fetchall()
    by_proj = defaultdict(Counter)
    for r in per_proj:
        by_proj[r["project_cwd"]][r["tool_name"]] += r["n"]
    ranked = sorted(by_proj.items(), key=lambda kv: -sum(kv[1].values()))[:15]
    widths = [22, 8, 14, 8, 26]
    row("project", "total", "top tool", "count", "", widths=widths)
    for proj, ctr in ranked:
        tot = sum(ctr.values())
        top_name, top_n = ctr.most_common(1)[0]
        row(short_project(proj), fmt_n(tot), top_name, fmt_n(top_n),
            bar(top_n, tot),
            widths=widths)


def section_tool_specific(conn, since_iso, project):
    h1("Tool-specific — the juice")
    where, params = _where(since_iso, project, table="tool_calls")

    def _fetch(tool):
        return conn.execute(
            f"SELECT input_json FROM tool_calls WHERE {where} AND tool_name = ?",
            (*params, tool),
        ).fetchall()

    def _top(tool, key, n=10):
        counter = Counter()
        for r in _fetch(tool):
            try:
                d = json.loads(r["input_json"])
            except Exception:
                continue
            v = d.get(key) if isinstance(d, dict) else None
            if v:
                counter[str(v)] += 1
        return counter.most_common(n)

    h2("Top Bash commands (by description, top 10)")
    for desc, n in _top("Bash", "description"):
        row(fmt_n(n).rjust(5), trim(desc, 70))

    h2("Top Grep patterns (top 10)")
    for pat, n in _top("Grep", "pattern"):
        row(fmt_n(n).rjust(5), trim(pat, 70))

    h2("Top Read file_paths (top 15)")
    for fp, n in _top("Read", "file_path", n=15):
        row(fmt_n(n).rjust(5), trim(fp, 70))

    h2("Top Write file_paths (top 10)")
    for fp, n in _top("Write", "file_path"):
        row(fmt_n(n).rjust(5), trim(fp, 70))

    h2("Top Edit file_paths (top 10)")
    for fp, n in _top("Edit", "file_path"):
        row(fmt_n(n).rjust(5), trim(fp, 70))

    h2("Most-invoked Skills")
    for skill, n in _top("Skill", "skill"):
        row(fmt_n(n).rjust(5), skill)


def section_turn_behavior(conn, since_iso, project):
    h1("Turn behavior")
    where, params = _where(since_iso, project)

    h2("Stop reason distribution")
    rows = conn.execute(f"""
        SELECT COALESCE(stop_reason, '(none)') AS sr, COUNT(*) AS n
          FROM turns WHERE {where} GROUP BY sr ORDER BY n DESC
    """, params).fetchall()
    maxv = rows[0]["n"] if rows else 0
    for r in rows:
        row(r["sr"].ljust(18), fmt_n(r["n"]).rjust(8), bar(r["n"], maxv))

    h2("Iterations per turn (how many rounds a single turn needed)")
    rows = conn.execute(f"""
        SELECT iterations_count AS ic, COUNT(*) AS n
          FROM turns WHERE {where} AND ic IS NOT NULL GROUP BY ic ORDER BY ic
    """, params).fetchall()
    maxv = max((r["n"] for r in rows), default=0)
    for r in rows:
        row(f"{r['ic']} round".ljust(18), fmt_n(r["n"]).rjust(8), bar(r["n"], maxv))

    h2("Turn duration — percentiles (from system.turn_duration)")
    rows = conn.execute(f"""
        SELECT duration_ms FROM turns
         WHERE {where} AND duration_ms IS NOT NULL
         ORDER BY duration_ms
    """, params).fetchall()
    if rows:
        vals = [r["duration_ms"] for r in rows]
        def pct(p):
            i = int(len(vals) * p / 100)
            return vals[min(i, len(vals)-1)]
        row("n (with duration)", fmt_n(len(vals)))
        row("p50",               fmt_ms(pct(50)))
        row("p75",               fmt_ms(pct(75)))
        row("p90",               fmt_ms(pct(90)))
        row("p95",               fmt_ms(pct(95)))
        row("p99",               fmt_ms(pct(99)))
        row("max",               fmt_ms(vals[-1]))
        row("total active-ms",   fmt_ms(sum(vals)))
    else:
        row("(no duration data — system.turn_duration events haven't been joined)")


def section_thinking(conn, since_iso, project):
    h1("Thinking vs visible — where the output tokens go")
    where, params = _where(since_iso, project)
    r = conn.execute(f"""
        SELECT SUM(num_thinking_blocks)  AS tb,
               SUM(thinking_chars)       AS tc,
               SUM(num_text_blocks)      AS xb,
               SUM(text_chars)           AS xc,
               SUM(num_tool_uses)        AS tu,
               SUM(output_tokens)        AS out
          FROM turns WHERE {where}
    """, params).fetchone()
    total_chars = (r["tc"] or 0) + (r["xc"] or 0)
    if not total_chars:
        row("(no content character data yet — backfill may still be running)")
        return
    tpct = (r["tc"] or 0) / total_chars * 100
    xpct = (r["xc"] or 0) / total_chars * 100
    row("thinking blocks",  fmt_n(r["tb"]))
    row("thinking chars",   fmt_n(r["tc"]), f"{tpct:.1f}% of content")
    row("text blocks",      fmt_n(r["xb"]))
    row("text chars",       fmt_n(r["xc"]), f"{xpct:.1f}% of content")
    row("tool_use blocks",  fmt_n(r["tu"]))
    row("output tokens",    fmt_n(r["out"]))
    if r["tu"]:
        row("chars per tool_use", f"{total_chars / r['tu']:.0f}")


def section_user_activity(conn, since_iso, project):
    h1("User activity — prompts & screenshots")
    where, params = _where(since_iso, project, table="user_prompts")
    r = conn.execute(f"""
        SELECT SUM(is_real_prompt)         AS real_prompts,
               SUM(image_count)            AS images,
               SUM(tool_result_count)      AS tool_results,
               AVG(text_chars)             AS avg_len,
               COUNT(*)                    AS total
          FROM user_prompts WHERE {where}
    """, params).fetchone()
    row("real prompts",       fmt_n(r["real_prompts"]))
    row("tool_result wraps",  fmt_n(r["tool_results"]))
    row("images pasted",      fmt_n(r["images"]))
    row("avg chars/prompt",   f"{r['avg_len'] or 0:.0f}")
    row("total user events",  fmt_n(r["total"]))

    h2("Prompts per day (last 30)")
    rows = conn.execute(f"""
        SELECT substr(ts, 1, 10) AS day,
               SUM(is_real_prompt) AS prompts,
               SUM(image_count)    AS images
          FROM user_prompts
         WHERE {where}
         GROUP BY day ORDER BY day DESC LIMIT 30
    """, params).fetchall()
    maxv = max((r["prompts"] or 0) for r in rows) if rows else 0
    widths = [12, 9, 9, 26]
    row("day", "prompts", "images", "", widths=widths)
    for r in rows:
        row(r["day"], fmt_n(r["prompts"]), fmt_n(r["images"]),
            bar(r["prompts"] or 0, maxv), widths=widths)


def section_sessions(conn, since_iso, project):
    h1("Sessions — length + turns")
    where, params = _where(since_iso, project)
    rows = conn.execute(f"""
        SELECT session_id,
               MIN(ts) AS start, MAX(ts) AS end,
               COUNT(*) AS turns,
               SUM(output_tokens) AS out_tok,
               GROUP_CONCAT(DISTINCT project_cwd) AS projects
          FROM turns WHERE {where}
         GROUP BY session_id
         ORDER BY turns DESC
         LIMIT 15
    """, params).fetchall()
    widths = [22, 8, 10, 22, 10]
    row("session", "turns", "out_tok", "projects", "minutes", widths=widths)
    for r in rows:
        try:
            start = datetime.fromisoformat(r["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(r["end"].replace("Z", "+00:00"))
            mins = int((end - start).total_seconds() / 60)
        except Exception:
            mins = 0
        projs = ",".join(sorted({short_project(p) for p in (r["projects"] or "").split(",") if p}))
        row(r["session_id"][:8] + "…", fmt_n(r["turns"]), fmt_n(r["out_tok"]),
            trim(projs, 20), f"{mins}m",
            widths=widths)


def section_hourly_heatmap(conn, since_iso, project):
    h1("Hourly heatmap (PT) — when do I burn turns")
    where, params = _where(since_iso, project)
    rows = conn.execute(f"""
        SELECT ts, output_tokens FROM turns WHERE {where}
    """, params).fetchall()
    by_hour = Counter()
    for r in rows:
        try:
            t = datetime.fromisoformat(r["ts"].replace("Z", "+00:00")).astimezone(PT)
            by_hour[t.hour] += 1
        except Exception:
            continue
    maxv = max(by_hour.values() or [0])
    for h in range(24):
        n = by_hour.get(h, 0)
        label = f"{h:02d}:00"
        print(f"  {label}  {str(n).rjust(6)}  {bar(n, maxv, width=48)}")


def section_errors(conn, since_iso, project):
    h1("Errors")
    where, params = _where(since_iso, project)
    r = conn.execute(f"""
        SELECT SUM(is_api_error) AS api_err, COUNT(*) AS total
          FROM turns WHERE {where}
    """, params).fetchone()
    row("api error turns", fmt_n(r["api_err"] or 0), f"/{fmt_n(r['total'])}")

    where_tr, params_tr = _where(since_iso, project, table="tool_results")
    r2 = conn.execute(f"""
        SELECT SUM(is_error) AS errs, COUNT(*) AS total
          FROM tool_results WHERE {where_tr}
    """, params_tr).fetchone()
    pct = (r2["errs"] or 0) / (r2["total"] or 1) * 100
    row("tool_result errors", fmt_n(r2["errs"] or 0), f"/{fmt_n(r2['total'])} ({pct:.2f}%)")

    h2("Most-erroring tools")
    rows = conn.execute(f"""
        SELECT tc.tool_name, SUM(tr.is_error) AS errs, COUNT(*) AS total
          FROM tool_calls tc
          JOIN tool_results tr USING (tool_use_id)
         WHERE {where.replace('ts', 'tc.ts')}
         GROUP BY tc.tool_name
        HAVING errs > 0
         ORDER BY errs DESC
         LIMIT 15
    """, params).fetchall()
    widths = [20, 8, 8, 10]
    row("tool", "errors", "total", "rate", widths=widths)
    for r in rows:
        rate = (r["errs"] or 0) / (r["total"] or 1) * 100
        row(r["tool_name"], fmt_n(r["errs"]), fmt_n(r["total"]), f"{rate:.1f}%", widths=widths)


def section_permission_modes(conn, since_iso, project):
    h1("Permission modes — what mode am I usually in")
    where, params = _where(since_iso, project)
    rows = conn.execute(f"""
        SELECT COALESCE(permission_mode, '(none)') AS pm, COUNT(*) AS n
          FROM turns WHERE {where} GROUP BY pm ORDER BY n DESC
    """, params).fetchall()
    maxv = rows[0]["n"] if rows else 0
    for r in rows:
        row(r["pm"].ljust(18), fmt_n(r["n"]).rjust(8), bar(r["n"], maxv))


def section_sidechain(conn, since_iso, project):
    h1("Sidechain tax — subagent share")
    where, params = _where(since_iso, project)
    r = conn.execute(f"""
        SELECT is_sidechain,
               COUNT(*)            AS turns,
               SUM(output_tokens)  AS out_tok,
               SUM(input_tokens + cache_read_input_tokens + cache_creation_input_tokens) AS in_tok
          FROM turns WHERE {where} GROUP BY is_sidechain
    """, params).fetchall()
    total_out = sum((x["out_tok"] or 0) for x in r) or 1
    for x in r:
        label = "subagent" if x["is_sidechain"] else "main thread"
        pct = (x["out_tok"] or 0) / total_out * 100
        row(label.ljust(14), fmt_n(x["turns"]), fmt_n(x["out_tok"]), fmt_n(x["in_tok"]), f"{pct:.1f}% out")


# ------------------------------------------------------------------
# where clause builder — all sections share these filters
# ------------------------------------------------------------------

def _where(since_iso, project, table="turns"):
    conds = ["ts >= ?"]
    params = [since_iso]
    if project:
        # tool_results has no project_cwd column — look up via tool_calls
        if table == "tool_results":
            conds.append("tool_use_id IN (SELECT tool_use_id FROM tool_calls WHERE project_cwd LIKE ?)")
        else:
            conds.append("project_cwd LIKE ?")
        params.append(f"%{project}%")
    return " AND ".join(conds), params


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30, help="window size in days (default 30)")
    ap.add_argument("--today", action="store_true", help="just today (PT)")
    ap.add_argument("--project", type=str, default=None, help="filter by project-name substring")
    ap.add_argument("--section", type=str, default=None,
                    help="only run this section (overview/tokens/projects/tools/tool_specific/behavior/thinking/user/sessions/heatmap/errors/perm/sidechain)")
    args = ap.parse_args()

    conn = dbmod.connect()
    since_iso, label = build_window(args)

    sections = [
        ("overview",      section_overview),
        ("tokens",        section_token_burn),
        ("projects",      section_projects),
        ("tools",         section_tools),
        ("tool_specific", section_tool_specific),
        ("behavior",      section_turn_behavior),
        ("thinking",      section_thinking),
        ("user",          section_user_activity),
        ("sessions",      section_sessions),
        ("heatmap",       section_hourly_heatmap),
        ("errors",        section_errors),
        ("perm",          section_permission_modes),
        ("sidechain",     section_sidechain),
    ]

    for name, fn in sections:
        if args.section and name != args.section:
            continue
        try:
            if name == "overview":
                fn(conn, since_iso, label)
            else:
                fn(conn, since_iso, args.project)
        except Exception as e:
            print(f"\n[!] section '{name}' failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
