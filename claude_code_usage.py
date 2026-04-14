"""
Claude Code usage — personalized dashboard with pacing, 99%-by-Friday
targeting, active-hour rate conversion, ASCII charts, search, and
Anthropic Max-plan drift validation.

Data sources:
  1. Live API: GET https://api.anthropic.com/api/oauth/usage — Anthropic's
     authoritative weekly/session quota (% utilization + reset timestamps)
  2. Local SQLite at _infrastructure/cc_usage/data/claude_usage.db — backfilled
     per-turn token counts parsed from ~/.claude/projects/*/*.jsonl

Each CLI invocation records a fresh snapshot to the `snapshots` table, so
historical pacing (recent burn rate, projection to landing) is always
available from the rolling log.

## Auth

Reads the Claude Code OAuth access token from the macOS keychain. Pure read,
never writes, never refreshes — refreshing rotates the token and kicks the
live CLI back to /login, so the script deliberately avoids that path.

The `anthropic-beta: oauth-2025-04-20` header is required to unlock OAuth on
`/api/oauth/*` — without it the server returns "OAuth authentication is
currently not supported".

## CLI

    cc-usage                       # panel + pacing (records snapshot)
    cc-usage --report              # + tokens by model/project + session list
    cc-usage --charts              # + hourly & daily burn ASCII charts
    cc-usage --search my-repo      # filter everything by project substring
    cc-usage --validate            # Max plan drift check (snapshot Δ% vs token burn)
    cc-usage --json                # raw API JSON
    cc-usage --plain               # panel without writing snapshot
    cc-usage --target 95           # custom weekly target %

Aliased to `cc-usage` in ~/.zshrc.
"""

import argparse
import getpass
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# Sibling import — claude_usage_db.py lives next to this file in
# _infrastructure/cc_usage/. Add our own directory to sys.path so the import
# works no matter where the interpreter is invoked from (launchd, zshrc alias,
# cron, or a `cd elsewhere && python3 /path/to/claude_code_usage.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_usage_db as dbmod  # noqa: E402

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
USER_AGENT = "claude-cli/2.1.101 (external, cli)"
# Required to unlock OAuth on /api/oauth/* endpoints. Without this header
# the server returns 401 "OAuth authentication is currently not supported".
# Extracted from the Claude Code CLI binary (constant `GP`).
ANTHROPIC_BETA = "oauth-2025-04-20"
KEYCHAIN_SERVICE = "Claude Code-credentials"

# Multi-account registry.  Each key maps to the keychain service name and a
# human-readable label.  The overflow account absorbs usage after the primary
# hits its weekly cap — see MULTI_ACCOUNT_PLAN.md for the full rationale.
ACCOUNTS = {
    "primary":  {"keychain": "Claude Code-credentials",          "label": "Max 20x", "tier": "max_20x"},
    "overflow": {"keychain": "Claude Code-credentials-bae1e975", "label": "Pro",     "tier": "pro"},
}

# Local wall-clock timezone for human-friendly displays ("4:28pm", "Sat Apr 11").
# Override with the CC_USAGE_TZ env var (any IANA zone name, e.g. "Europe/Berlin").
# Defaults to America/Los_Angeles to match the Anthropic quota reset convention.
PT = ZoneInfo(os.environ.get("CC_USAGE_TZ", "America/Los_Angeles"))
DEFAULT_TARGET = 99.0


# ---------- auth + fetch ----------

def _load_access_token(keychain_service=KEYCHAIN_SERVICE):
    result = subprocess.run(
        [
            "security", "find-generic-password",
            "-s", keychain_service,
            "-a", getpass.getuser(),
            "-w",
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Claude Code keychain entry not found ({keychain_service}): "
            f"{result.stderr.strip() or 'unknown error'}"
        )
    return json.loads(result.stdout)["claudeAiOauth"]["accessToken"]


def get_usage(keychain_service=KEYCHAIN_SERVICE):
    resp = requests.get(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {_load_access_token(keychain_service)}",
            "anthropic-beta": ANTHROPIC_BETA,
            "User-Agent": USER_AGENT,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------- time helpers ----------

def _parse_iso(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _fmt_reset(iso_ts):
    dt = _parse_iso(iso_ts)
    if not dt:
        return ""
    return dt.astimezone(PT).strftime("%a %b %-d, %-I:%M%p").replace(":00", "")


def _hours_until(iso_ts):
    dt = _parse_iso(iso_ts)
    if not dt:
        return 0.0
    return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds() / 3600)


def _hours_since(iso_ts):
    dt = _parse_iso(iso_ts)
    if not dt:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)


def _fmt_duration(hours):
    if hours < 1 / 60:
        return "<1m"
    if hours < 1:
        return f"{int(round(hours * 60))}m"
    if hours < 24:
        h = int(hours)
        m = int(round((hours - h) * 60))
        return f"{h}h {m}m" if m else f"{h}h"
    days = hours / 24
    if days < 10:
        return f"{days:.1f}d"
    return f"{int(round(days))}d"


def _bar(pct, width=50):
    pct = max(0, min(100, pct))
    filled = int(round((pct / 100) * width))
    return "█" * filled + "░" * (width - filled)


def _fmt_tokens(n):
    if n is None:
        return "—"
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def _short_proj(path):
    """
    Shorten a project cwd path for CLI display. Replaces the user's home
    directory with `~` so wide project paths like
    `/Users/alice/code/big-repo-name` collapse to `~/code/big-repo-name`.
    Then truncates to 40 chars to keep table columns aligned.
    """
    if not path:
        return "—"
    home = str(Path.home())
    if path.startswith(home):
        path = "~" + path[len(home):]
    return path[:40]


def _week_start_iso(reset_iso):
    """Weekly window = 168h before reset."""
    dt = _parse_iso(reset_iso)
    if not dt:
        return None
    return (dt - timedelta(hours=168)).isoformat()


def _session_start_iso(reset_iso):
    """Current session window = 5h before reset."""
    dt = _parse_iso(reset_iso)
    if not dt:
        return None
    return (dt - timedelta(hours=5)).isoformat()


# ---------- pace from snapshots ----------

def _recent_pace(conn, bucket_col, bucket_reset_col, current_reset_iso, current_pct):
    """
    Return (pct_per_day, hours_ago) from the oldest snapshot in the SAME
    window (same reset timestamp) that has a usable value. Returns None if
    we don't have enough history yet.
    """
    if not current_reset_iso:
        return None
    row = conn.execute(
        f"SELECT ts, {bucket_col} FROM snapshots "
        f"WHERE {bucket_reset_col} = ? AND {bucket_col} IS NOT NULL "
        f"ORDER BY ts ASC LIMIT 1",
        (current_reset_iso,),
    ).fetchone()
    if not row or row[bucket_col] is None:
        return None
    prev_ts = _parse_iso(row["ts"])
    if not prev_ts:
        return None
    hours = (datetime.now(timezone.utc) - prev_ts).total_seconds() / 3600
    if hours < 0.05:  # under 3 min — too noisy
        return None
    delta = current_pct - row[bucket_col]
    if delta < 0:
        return None
    return ((delta / hours) * 24, hours)


def _recent_dollar_pace(conn, extra_reset_iso, current_used_cents):
    if not extra_reset_iso:
        return None
    row = conn.execute(
        "SELECT ts, extra_used_cents FROM snapshots "
        "WHERE extra_reset = ? AND extra_used_cents IS NOT NULL "
        "ORDER BY ts ASC LIMIT 1",
        (extra_reset_iso,),
    ).fetchone()
    if not row or row["extra_used_cents"] is None:
        return None
    prev_ts = _parse_iso(row["ts"])
    if not prev_ts:
        return None
    hours = (datetime.now(timezone.utc) - prev_ts).total_seconds() / 3600
    if hours < 0.05:
        return None
    delta_dollars = (current_used_cents - row["extra_used_cents"]) / 100.0
    if delta_dollars < 0:
        return None
    return ((delta_dollars / hours) * 24, hours)


def _dollar_pace_since_last_reset(conn, current_used_cents, max_lookback_hours=24 * 40):
    """Compute $/day pace across the current monthly cycle, inferring the
    cycle boundary from snapshot history (no `extra_reset_iso` required).

    Walks snapshots oldest→newest within the lookback window. A monthly
    reset shows up as `extra_used_cents` decreasing between two adjacent
    snapshots (the counter drops back to 0). The most recent such drop
    is treated as the start of the current cycle. If no drops are
    observed, the oldest snapshot in the window is treated as the start.

    Returns `(dollars_per_day, lookback_hours, delta_dollars)` or None if
    there's insufficient data or zero movement. Callers should interpret
    `delta_dollars == 0` + `lookback_hours small` as "counter hasn't
    moved yet, wait longer" vs `lookback_hours large` as "you're genuinely
    not burning extra right now."
    """
    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(hours=max_lookback_hours)
    ).isoformat()
    rows = conn.execute(
        "SELECT ts, extra_used_cents FROM snapshots "
        "WHERE ts >= ? AND extra_used_cents IS NOT NULL "
        "ORDER BY ts ASC",
        (cutoff_iso,),
    ).fetchall()
    if not rows:
        return None

    # Find the most recent reset (drop). Anchor is the snapshot immediately
    # after that drop. If no drops, anchor = oldest row in the window.
    anchor = rows[0]
    for i in range(len(rows) - 1):
        if rows[i]["extra_used_cents"] > rows[i + 1]["extra_used_cents"]:
            anchor = rows[i + 1]

    anchor_ts = _parse_iso(anchor["ts"])
    if not anchor_ts:
        return None
    hours = (datetime.now(timezone.utc) - anchor_ts).total_seconds() / 3600
    if hours < 1.0:
        return None  # not enough elapsed time to compute anything meaningful

    delta_dollars = (current_used_cents - anchor["extra_used_cents"]) / 100.0
    if delta_dollars < 0:
        delta_dollars = 0.0  # defensive; shouldn't happen given anchor logic
    per_day = (delta_dollars / hours) * 24 if hours > 0 else 0
    return (per_day, hours, delta_dollars)


def _status(recent, safe):
    """Coach voice: 'pull back' not 'slow down'."""
    if safe <= 0:
        return "OVER CAP"
    if recent is None:
        return "—"
    ratio = recent / safe
    if ratio >= 1.5:
        return "PULL BACK HARD"
    if ratio >= 1.15:
        return "pull back"
    if ratio >= 0.85:
        return "on pace"
    return "plenty of headroom"


# ---------- active-hour rate (the "real work" unit) ----------

def _active_hour_stats(conn, since_iso, project_filter=None, account=None):
    """
    An 'active hour' = a distinct calendar hour (UTC bucket — consistent,
    not drifting with DST) where at least one non-sidechain assistant turn
    was produced. Translating %-quota → hours uses this as the base unit,
    so 'tomorrow you can work 1.28 active hours' is an honest number: it
    already excludes background/idle time.
    """
    where = "ts >= ? AND is_sidechain = 0"
    params = [since_iso]
    if project_filter:
        where += " AND project_cwd LIKE ?"
        params.append(f"%{project_filter}%")
    if account:
        where += " AND COALESCE(account, 'primary') = ?"
        params.append(account)
    row = conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT strftime('%Y-%m-%d %H', ts)) AS active_hours,
            COUNT(*) AS turns,
            SUM(input_tokens + output_tokens + cache_creation_input_tokens) AS tokens
        FROM turns
        WHERE {where}
        """,
        params,
    ).fetchone()
    return {
        "active_hours": row["active_hours"] or 0,
        "turns": row["turns"] or 0,
        "tokens": row["tokens"] or 0,
    }


def _pull_back_plan(current_pct, target_pct, hours_left, active_hours_so_far):
    """
    Given where we are in the week and how many active hours have produced
    the current %, compute:
      - pct_per_active_hour       (observed rate this week)
      - daily_budget_pct          (linear-to-target %/day)
      - active_hours_per_day_budget  (how many active hours per day to land on target)
      - tomorrow_budget_hours     (same thing, for tomorrow specifically)
    """
    if hours_left <= 0 or active_hours_so_far <= 0:
        return None
    rate = current_pct / active_hours_so_far
    if rate <= 0:
        return None
    days_left = hours_left / 24
    remaining_pct = max(0.0, target_pct - current_pct)
    daily_budget_pct = remaining_pct / days_left
    daily_hours = daily_budget_pct / rate
    return {
        "rate_pct_per_hour": rate,
        "daily_budget_pct": daily_budget_pct,
        "daily_hours": daily_hours,
        "tomorrow_hours": daily_hours,  # today is today; "tomorrow's allowance" = 1 day's budget
        "days_left": days_left,
    }


# ---------- panel ----------

def _print_bucket_row(label, block, bucket_col, reset_col, conn, target_pct, is_session=False):
    if not block:
        return None
    used = block.get("utilization", 0) or 0
    remaining = 100 - used
    reset_iso = block.get("resets_at")
    hours_left = _hours_until(reset_iso)
    hours_elapsed = 168 - hours_left if reset_iso and not is_session else 0

    print(f"\n  {label}")
    print(f"  {_bar(used)}")
    print(
        f"  {used:5.1f}% used · {remaining:5.1f}% left · "
        f"{_fmt_duration(hours_left)} to reset ({_fmt_reset(reset_iso)})"
    )

    if hours_left <= 0:
        return None

    pace = _recent_pace(conn, bucket_col, reset_col, reset_iso, used)

    if is_session:
        safe_h = remaining / hours_left if hours_left > 0 else 0
        line = f"  safe: {safe_h:5.2f}%/h"
        if pace:
            recent_per_day, lookback_h = pace
            recent_h = recent_per_day / 24
            line += (
                f"   ·   recent: {recent_h:5.2f}%/h "
                f"over {_fmt_duration(lookback_h)}   →   {_status(recent_h, safe_h)}"
            )
        print(line)
        if pace and pace[0] > 0:
            recent_h = pace[0] / 24
            if recent_h > 0:
                burnout_h = remaining / recent_h
                if burnout_h < hours_left:
                    print(
                        f"  at current pace you hit 100% in {_fmt_duration(burnout_h)} "
                        f"({_fmt_duration(hours_left - burnout_h)} before reset)"
                    )
        # active-hour rate within this 5h window
        session_start = _session_start_iso(reset_iso)
        if session_start:
            sstats = _active_hour_stats(conn, session_start)
            if sstats["active_hours"] >= 1 and used > 0:
                rate = used / sstats["active_hours"]
                headroom_hours = remaining / rate if rate > 0 else 0
                print(
                    f"  session rate: {rate:5.2f}%/active-hour "
                    f"({sstats['active_hours']}h · {sstats['turns']} turns) "
                    f"→ {headroom_hours:4.2f}h of work fits in the {remaining:.0f}% remaining"
                )
        return None

    # weekly bucket — add 99%-by-Friday math
    days_left = hours_left / 24
    safe_to_target = max(0.0, (target_pct - used) / days_left) if days_left > 0 else 0
    ideal_now = (hours_elapsed / 168) * target_pct
    vs_ideal = used - ideal_now

    # "on-pace-for-target" line
    direction = "AHEAD" if vs_ideal > 0 else ("behind" if vs_ideal < -0.5 else "on track")
    print(
        f"  on-pace-for-{int(target_pct)}% baseline: {ideal_now:5.2f}% "
        f"(you're {'+' if vs_ideal >= 0 else ''}{vs_ideal:5.2f}% {direction})"
    )

    # safe burn for hitting target
    print(
        f"  to land at {int(target_pct)}% by {_fmt_reset(reset_iso)}: "
        f"{safe_to_target:5.2f}%/day budget for {_fmt_duration(hours_left)}"
    )

    if pace:
        recent_per_day, lookback_h = pace
        projected = used + (recent_per_day * days_left)
        status = _status(recent_per_day, safe_to_target)
        print(
            f"  recent burn: {recent_per_day:5.2f}%/day over last "
            f"{_fmt_duration(lookback_h)}   →   projected landing "
            f"{projected:5.1f}%  ({status})"
        )

    return (label, safe_to_target, used, reset_iso)


# ---------- reports ----------

def _today_session_report(conn, reset_iso_utc, project_filter=None):
    where = "ts >= ?"
    params = [reset_iso_utc]
    if project_filter:
        where += " AND project_cwd LIKE ?"
        params.append(f"%{project_filter}%")
    rows = conn.execute(
        f"""
        SELECT
            session_id,
            project_cwd,
            COUNT(*) AS turns,
            MIN(ts) AS first_ts,
            MAX(ts) AS last_ts,
            SUM(input_tokens) AS in_tok,
            SUM(output_tokens) AS out_tok,
            SUM(cache_creation_input_tokens) AS cache_new,
            SUM(cache_read_input_tokens) AS cache_read,
            SUM(CASE WHEN is_sidechain = 1 THEN 1 ELSE 0 END) AS sidechain_turns,
            (SELECT model FROM turns t2 WHERE t2.session_id = t.session_id
             GROUP BY model ORDER BY COUNT(*) DESC LIMIT 1) AS top_model
        FROM turns t
        WHERE {where}
        GROUP BY session_id
        ORDER BY SUM(input_tokens + output_tokens + cache_creation_input_tokens) DESC
        """,
        params,
    ).fetchall()
    return rows


def _model_breakdown(conn, reset_iso_utc, project_filter=None):
    where = "ts >= ?"
    params = [reset_iso_utc]
    if project_filter:
        where += " AND project_cwd LIKE ?"
        params.append(f"%{project_filter}%")
    return conn.execute(
        f"""
        SELECT
            model,
            COUNT(*) AS turns,
            COUNT(DISTINCT session_id) AS sessions,
            SUM(input_tokens) AS in_tok,
            SUM(output_tokens) AS out_tok,
            SUM(cache_creation_input_tokens) AS cache_new,
            SUM(cache_read_input_tokens) AS cache_read
        FROM turns
        WHERE {where}
        GROUP BY model
        ORDER BY SUM(input_tokens + output_tokens + cache_creation_input_tokens) DESC
        """,
        params,
    ).fetchall()


def _project_breakdown(conn, reset_iso_utc, limit=10, project_filter=None):
    where = "ts >= ? AND project_cwd IS NOT NULL"
    params = [reset_iso_utc]
    if project_filter:
        where += " AND project_cwd LIKE ?"
        params.append(f"%{project_filter}%")
    params.append(limit)
    return conn.execute(
        f"""
        SELECT
            project_cwd,
            COUNT(*) AS turns,
            COUNT(DISTINCT session_id) AS sessions,
            SUM(input_tokens) AS in_tok,
            SUM(output_tokens) AS out_tok,
            SUM(cache_creation_input_tokens) AS cache_new,
            SUM(cache_read_input_tokens) AS cache_read
        FROM turns
        WHERE {where}
        GROUP BY project_cwd
        ORDER BY SUM(input_tokens + output_tokens + cache_creation_input_tokens) DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


def _print_report(conn, reset_iso_utc, project_filter=None):
    suffix = f"  (filter: project ~ '{project_filter}')" if project_filter else ""
    print(f"\n  ─ Since the weekly reset ─{suffix}")
    print(f"  window start: {_fmt_reset(reset_iso_utc)} PT")

    models = _model_breakdown(conn, reset_iso_utc, project_filter)
    if models:
        print("\n  tokens by model:")
        print(f"    {'model':<28} {'turns':>6} {'sess':>5} {'input':>10} {'output':>10} {'cache-new':>10} {'cache-rd':>10}")
        for r in models:
            print(
                f"    {(r['model'] or '—'):<28} {r['turns']:>6} {r['sessions']:>5} "
                f"{_fmt_tokens(r['in_tok']):>10} {_fmt_tokens(r['out_tok']):>10} "
                f"{_fmt_tokens(r['cache_new']):>10} {_fmt_tokens(r['cache_read']):>10}"
            )

    projects = _project_breakdown(conn, reset_iso_utc, project_filter=project_filter)
    if projects:
        print("\n  tokens by project (top 10):")
        print(f"    {'project':<42} {'turns':>6} {'sess':>5} {'input':>10} {'output':>10} {'cache-new':>10}")
        for r in projects:
            print(
                f"    {_short_proj(r['project_cwd']):<42} {r['turns']:>6} "
                f"{r['sessions']:>5} {_fmt_tokens(r['in_tok']):>10} "
                f"{_fmt_tokens(r['out_tok']):>10} {_fmt_tokens(r['cache_new']):>10}"
            )

    sessions = _today_session_report(conn, reset_iso_utc, project_filter)
    if sessions:
        print(f"\n  sessions this week ({len(sessions)}):")
        print(f"    {'started':<16} {'proj':<28} {'turns':>6} {'in+out':>10} {'cache-new':>10} {'model':<24}")
        for r in sessions:
            started_pt = _parse_iso(r["first_ts"]).astimezone(PT).strftime("%a %-I:%M%p")
            combined = (r["in_tok"] or 0) + (r["out_tok"] or 0)
            print(
                f"    {started_pt:<16} "
                f"{_short_proj(r['project_cwd'])[:28]:<28} "
                f"{r['turns']:>6} {_fmt_tokens(combined):>10} "
                f"{_fmt_tokens(r['cache_new']):>10} "
                f"{(r['top_model'] or '—'):<24}"
            )


# ---------- charts ----------

def _hourly_chart(conn, since_iso, project_filter=None, width=40, title=None):
    """Hourly bars since `since_iso` — one row per active UTC hour."""
    where = "ts >= ?"
    params = [since_iso]
    if project_filter:
        where += " AND project_cwd LIKE ?"
        params.append(f"%{project_filter}%")
    rows = conn.execute(
        f"""
        SELECT
            strftime('%Y-%m-%d %H', ts) AS hour_utc,
            COUNT(*) AS turns,
            SUM(cache_creation_input_tokens) AS cache_new,
            SUM(input_tokens + output_tokens + cache_creation_input_tokens) AS total_new
        FROM turns
        WHERE {where}
        GROUP BY hour_utc
        ORDER BY hour_utc
        """,
        params,
    ).fetchall()
    if not rows:
        print("\n  (no hourly data yet)")
        return
    max_val = max((r["total_new"] or 0) for r in rows) or 1
    print(f"\n  {title or 'hourly burn'}")
    print(f"  ({len(rows)} active hours · scale = input+output+cache-new)")
    for r in rows:
        dt = datetime.strptime(r["hour_utc"] + ":00:00+00:00", "%Y-%m-%d %H:%M:%S%z")
        pt_dt = dt.astimezone(PT)
        val = r["total_new"] or 0
        bar_len = int(round((val / max_val) * width))
        bar_len = max(1, bar_len) if val else 0
        label = pt_dt.strftime("%a %-I%p")
        bar = "█" * bar_len + "·" * (width - bar_len)
        print(f"  {label:<8} {bar}  {r['turns']:>4}t · {_fmt_tokens(val):>7}")


def _daily_chart(conn, days=14, project_filter=None, width=40):
    """
    One bar per PT calendar day over the last N days. Buckets in Python on
    PT (not SQLite UTC) so 'today' matches the hourly chart.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days + 1)).isoformat()
    where = "ts >= ?"
    params = [since]
    if project_filter:
        where += " AND project_cwd LIKE ?"
        params.append(f"%{project_filter}%")
    rows = conn.execute(
        f"""
        SELECT ts, session_id, input_tokens, output_tokens,
               cache_creation_input_tokens
        FROM turns
        WHERE {where}
        ORDER BY ts
        """,
        params,
    ).fetchall()
    if not rows:
        print("\n  (no daily data yet)")
        return

    # Bucket in PT
    today_pt = datetime.now(PT).date()
    cutoff = today_pt - timedelta(days=days - 1)
    buckets = defaultdict(lambda: {
        "turns": 0, "sessions": set(), "hours": set(), "tokens": 0,
    })
    for r in rows:
        dt = _parse_iso(r["ts"])
        if not dt:
            continue
        pt_dt = dt.astimezone(PT)
        day = pt_dt.date()
        if day < cutoff:
            continue
        b = buckets[day]
        b["turns"] += 1
        b["sessions"].add(r["session_id"])
        b["hours"].add(pt_dt.strftime("%Y-%m-%d %H"))
        b["tokens"] += (
            (r["input_tokens"] or 0)
            + (r["output_tokens"] or 0)
            + (r["cache_creation_input_tokens"] or 0)
        )
    if not buckets:
        print("\n  (no daily data in window)")
        return
    max_val = max(b["tokens"] for b in buckets.values()) or 1
    print(f"\n  daily burn — last {days} days (PT calendar)")
    print("  (scale = input+output+cache-new tokens)")
    for day in sorted(buckets.keys()):
        b = buckets[day]
        val = b["tokens"]
        bar_len = int(round((val / max_val) * width))
        bar_len = max(1, bar_len) if val else 0
        label = day.strftime("%a %b %-d")
        bar = "█" * bar_len + "·" * (width - bar_len)
        print(
            f"  {label:<11} {bar}  {len(b['hours']):>2}h · "
            f"{len(b['sessions']):>2}s · {b['turns']:>5}t · {_fmt_tokens(val):>7}"
        )


# ---------- search ----------

def _print_search(conn, substring, limit=20):
    print(f"\n  Search: project_cwd LIKE '%{substring}%'")
    rows = conn.execute(
        """
        SELECT
            project_cwd,
            COUNT(*) AS turns,
            COUNT(DISTINCT session_id) AS sessions,
            MIN(ts) AS first_ts,
            MAX(ts) AS last_ts,
            SUM(input_tokens) AS in_tok,
            SUM(output_tokens) AS out_tok,
            SUM(cache_creation_input_tokens) AS cache_new,
            SUM(cache_read_input_tokens) AS cache_read
        FROM turns
        WHERE project_cwd LIKE ?
        GROUP BY project_cwd
        ORDER BY SUM(input_tokens + output_tokens + cache_creation_input_tokens) DESC
        LIMIT ?
        """,
        (f"%{substring}%", limit),
    ).fetchall()
    if not rows:
        print("  (no matches)")
        return
    print(f"  {'project':<44} {'sess':>4} {'turns':>6} {'first':<14} {'last':<14} {'cache-new':>10}")
    for r in rows:
        first = _parse_iso(r["first_ts"]).astimezone(PT).strftime("%b %-d %-I%p")
        last = _parse_iso(r["last_ts"]).astimezone(PT).strftime("%b %-d %-I%p")
        print(
            f"  {_short_proj(r['project_cwd']):<44} "
            f"{r['sessions']:>4} {r['turns']:>6} "
            f"{first:<14} {last:<14} "
            f"{_fmt_tokens(r['cache_new']):>10}"
        )


# ---------- Max plan validation (snapshot Δ% vs token burn) ----------

def _validate_anthropic(conn):
    """
    Between every pair of adjacent snapshots in the CURRENT weekly window,
    compare API-reported Δ quota% against token burn in the same interval.
    If the %/Mtok ratio drifts over time, that's evidence Anthropic is
    metering the Max plan differently than on day 1 — either cheaper
    (headroom) or more expensive (cap is timing out sooner).
    """
    snaps = conn.execute("""
        SELECT ts, seven_day_pct, seven_day_reset
        FROM snapshots
        WHERE seven_day_pct IS NOT NULL
        ORDER BY ts
    """).fetchall()
    if len(snaps) < 2:
        print("\n  Max plan validation")
        print("  (need ≥2 snapshots in the same weekly window — run cc-usage a few more times)")
        return

    windows = defaultdict(list)
    for s in snaps:
        windows[s["seven_day_reset"]].append(s)

    print("\n  Max plan validation — snapshot Δ% vs token burn")
    print("  ─ compares API's metered weekly% against local turn-token counts ─")
    print(f"  {'window':<10} {'interval':<25} {'Δ %':>7} {'Δ tokens':>12} {'%/Mtok':>9}  {'notes'}")

    ratios = []
    for reset, rows in windows.items():
        if len(rows) < 2:
            continue
        reset_short = _parse_iso(reset).astimezone(PT).strftime("%b %-d") if reset else "—"
        for i in range(1, len(rows)):
            a, b = rows[i - 1], rows[i]
            delta_pct = (b["seven_day_pct"] or 0) - (a["seven_day_pct"] or 0)
            if delta_pct <= 0.01:
                continue
            sums = conn.execute(
                """
                SELECT
                    SUM(input_tokens) AS in_tok,
                    SUM(output_tokens) AS out_tok,
                    SUM(cache_creation_input_tokens) AS cache_new,
                    SUM(cache_read_input_tokens) AS cache_read
                FROM turns
                WHERE ts > ? AND ts <= ?
                """,
                (a["ts"], b["ts"]),
            ).fetchone()
            cache_new = sums["cache_new"] or 0
            inout = (sums["in_tok"] or 0) + (sums["out_tok"] or 0)
            total = cache_new + inout
            if total <= 0:
                continue
            ratio = delta_pct / (total / 1_000_000)
            ratios.append(ratio)
            a_pt = _parse_iso(a["ts"]).astimezone(PT).strftime("%a %-I:%M%p")
            b_pt = _parse_iso(b["ts"]).astimezone(PT).strftime("%-I:%M%p")
            print(
                f"  {reset_short:<10} {a_pt}→{b_pt:<12} "
                f"{delta_pct:>7.2f} {_fmt_tokens(total):>12} {ratio:>9.4f}"
            )

    if len(ratios) >= 3:
        avg = sum(ratios) / len(ratios)
        lo, hi = min(ratios), max(ratios)
        print()
        print(f"  avg  : {avg:.4f} %/Mtok")
        print(f"  range: {lo:.4f} → {hi:.4f}  (drift = {((hi-lo)/avg*100):.1f}%)")
        # interpretation
        if hi - lo > avg * 0.5:
            print("  ⚠ >50% drift — Anthropic's metering is NOT stable over the week.")
        elif hi - lo > avg * 0.2:
            print("  ~ 20-50% drift — within reasonable noise, no obvious anomaly.")
        else:
            print("  ✓ <20% drift — metering appears consistent.")
    else:
        print("\n  (not enough valid intervals yet — keep running cc-usage periodically)")


# ---------- main panel ----------

def print_panel(
    data=None,
    conn=None,
    record=True,
    report=False,
    charts=False,
    target=DEFAULT_TARGET,
    project_filter=None,
):
    if conn is None:
        conn = dbmod.connect()
    # Resolve `data`: prefer a live fetch, fall back to the most recent DB
    # snapshot on any error (429, network, token refresh, etc.). Matches the
    # widget's fallback policy — transient API issues should never crash the
    # panel, and a slightly stale snapshot is always better than a traceback.
    # When we do fall back, we also run the same live-extrapolation the
    # widget uses so the CLI and widget stay numerically consistent — no
    # "widget says 45%, cc-usage says 39%" skew just because the API is
    # refusing us right now.
    live_fetched = False
    if data is None:
        try:
            data = get_usage()
            live_fetched = True
        except Exception as e:
            row = dbmod.latest_snapshot(conn)
            if row and row["raw_json"]:
                try:
                    data = json.loads(row["raw_json"])
                    age_min = max(
                        0,
                        (
                            datetime.now(timezone.utc) - _parse_iso(row["ts"])
                        ).total_seconds() / 60,
                    ) if row["ts"] else None
                    age_str = (
                        f"{int(age_min)}m old" if age_min is not None else "stale"
                    )
                    _extrapolate_live(conn, data, row["ts"])
                    extra_info = data.get("_extrapolated") or {}
                    week_info = extra_info.get("week") or {}
                    session_info = extra_info.get("session") or {}
                    if week_info.get("applied") or session_info.get("applied"):
                        bits = []
                        if session_info.get("applied"):
                            bits.append(
                                f"session +{session_info.get('delta_pct', 0):.1f}%"
                            )
                        if week_info.get("applied"):
                            bits.append(
                                f"week +{week_info.get('delta_pct', 0):.1f}%"
                            )
                        detail = " · ".join(bits)
                        print(
                            f"  ⚠  live fetch failed ({type(e).__name__}); "
                            f"anchor {age_str}, extrapolated from turns ({detail})"
                        )
                    else:
                        print(
                            f"  ⚠  live fetch failed ({type(e).__name__}); "
                            f"showing last DB snapshot ({age_str})"
                        )
                except Exception:
                    raise e
            else:
                raise
    # Only record a new snapshot if `data` came from a fresh API call.
    # Replaying a stale snapshot row would double-count it.
    if record and live_fetched:
        dbmod.insert_snapshot(
            conn,
            ts=datetime.now(timezone.utc).isoformat(),
            source="cli",
            data=data,
        )

    now_pt = datetime.now(timezone.utc).astimezone(PT)
    print()
    title = f"  Claude Code usage · {now_pt.strftime('%a %b %-d, %-I:%M%p %Z')} · target {int(target)}%"
    if project_filter:
        title += f"  ·  filter: {project_filter}"
    print(title)
    print("  " + "─" * 72)

    constraint = None

    _print_bucket_row(
        "Current session (5h window)",
        data.get("five_hour"),
        "five_hour_pct", "five_hour_reset",
        conn, target, is_session=True,
    )

    for label, key, col, reset_col in [
        ("Weekly — all models",    "seven_day",        "seven_day_pct",        "seven_day_reset"),
        ("Weekly — Sonnet only",   "seven_day_sonnet", "seven_day_sonnet_pct", "seven_day_sonnet_reset"),
        ("Weekly — Opus only",     "seven_day_opus",   "seven_day_opus_pct",   "seven_day_opus_reset"),
    ]:
        result = _print_bucket_row(label, data.get(key), col, reset_col, conn, target)
        if result:
            lbl, safe, used, reset_iso = result
            if constraint is None or safe < constraint[1]:
                constraint = (lbl, safe, used, reset_iso)

    # extra usage
    extra = data.get("extra_usage") or {}
    if extra.get("is_enabled"):
        used_pct = extra.get("utilization", 0) or 0
        spent = (extra.get("used_credits") or 0) / 100
        cap = (extra.get("monthly_limit") or 0) / 100
        remaining = cap - spent
        reset_iso = extra.get("resets_at")
        hours_left = _hours_until(reset_iso) if reset_iso else None

        print("\n  Extra usage ($ cap)")
        print(f"  {_bar(used_pct)}")
        if hours_left is not None:
            days_left = hours_left / 24
            print(
                f"  ${spent:7.2f} / ${cap:7.2f} spent · ${remaining:7.2f} left · "
                f"{_fmt_duration(hours_left)} to reset ({_fmt_reset(reset_iso)})"
            )
            safe_per_day = remaining / days_left if days_left > 0 else 0
            line = f"  safe pace: ${safe_per_day:5.2f}/day"
            pace = _recent_dollar_pace(conn, reset_iso, extra.get("used_credits") or 0)
            if pace:
                recent_per_day, lookback_h = pace
                status = _status(recent_per_day, safe_per_day)
                line += (
                    f"   ·   recent: ${recent_per_day:5.2f}/day over "
                    f"{_fmt_duration(lookback_h)}   →   {status}"
                )
            print(line)

    # constraint summary + TOMORROW'S BUDGET in active hours
    if constraint:
        lbl, safe, used, reset_iso = constraint
        week_start_iso = _week_start_iso(reset_iso)
        print()
        print("  " + "─" * 72)
        print(
            f"  Constraint: {lbl} — keep burn under "
            f"{safe:5.2f}%/day to land at {int(target)}%."
        )

        stats = _active_hour_stats(conn, week_start_iso, project_filter) if week_start_iso else None
        if stats and stats["active_hours"] >= 2:
            plan = _pull_back_plan(
                current_pct=used,
                target_pct=target,
                hours_left=_hours_until(reset_iso),
                active_hours_so_far=stats["active_hours"],
            )
            if plan:
                rate = plan["rate_pct_per_hour"]
                print()
                print(
                    f"  Observed rate this week : {rate:5.2f}%/active-hour "
                    f"(over {stats['active_hours']} active hours · {stats['turns']} turns)"
                )
                status = "PULL BACK" if plan["daily_hours"] < 4 else "steady"
                print(
                    f"  Tomorrow's budget       : {plan['daily_hours']:5.2f} active hours "
                    f"({plan['daily_budget_pct']:5.2f}%/day)   →   {status}"
                )
                if plan["daily_hours"] < 2:
                    print("  ⚠ under 2h/day — you're pushing the cap; consider lighter work tomorrow")
                elif plan["daily_hours"] > 8:
                    print("  ✓ lots of headroom — you could do a heavy day tomorrow")

    if charts:
        five_hour = data.get("five_hour") or {}
        five_reset = five_hour.get("resets_at")
        if five_reset:
            sess_start = _session_start_iso(five_reset)
            _hourly_chart(
                conn, sess_start, project_filter,
                title="session burn — current 5h window",
            )

        seven_day = data.get("seven_day") or {}
        reset_iso = seven_day.get("resets_at")
        if reset_iso:
            week_start = _week_start_iso(reset_iso)
            _hourly_chart(
                conn, week_start, project_filter,
                title="weekly burn — active hours since weekly reset",
            )
            _daily_chart(conn, days=14, project_filter=project_filter)

    if report:
        seven_day = data.get("seven_day") or {}
        reset_iso = seven_day.get("resets_at")
        if reset_iso:
            _print_report(conn, _week_start_iso(reset_iso), project_filter)

    print()


# ---------- live session probe ----------
#
# The DB backfill is not on a continuous schedule, so the DB can be hours
# stale behind the live JSONL files in ~/.claude/projects/. To power the
# widget's live session-length nudge we bypass the DB entirely and read
# the active session JSONL files directly. Cheap enough (one or two small
# files, ~once/min) and always fresh.
#
# Thresholds (band) are CANONICAL here — the widget JSX, the nag daemon, and
# the UserPromptSubmit hook all consume this same function so they agree on
# what "too long" means. Changing them in one place changes all three.

_BAND_ORDER = {"crit": 0, "warn": 1, "hint": 2, "good": 3}

# Opus cache-read price: $0.50/mtok. This is what you pay on EVERY reply
# to re-read the session's context from cache. Turn count is historical
# (sunk cost); cache-read cost per reply is forward-looking and is the
# number that should drive "should I handoff now?" decisions.
_OPUS_CACHE_READ_USD_PER_TOKEN = 0.50 / 1_000_000


def _cost_per_reply_usd(context_tokens):
    """Minimum per-reply cost in USD — just the cache re-read of session context.

    Doesn't include thinking, new user input, or tool output — those vary
    per turn. This is the FLOOR cost that's paid on every single reply
    regardless of what else happens. Drives the classification bands below.
    """
    if not context_tokens:
        return 0.0
    return context_tokens * _OPUS_CACHE_READ_USD_PER_TOKEN


def _classify_session(turns, context_k):
    """Return (band, status_word) for a session based on per-reply cost.

    Classification is driven purely by context_k, because context size
    determines forward-looking per-reply cost. Turn count is NOT used —
    it's a historical (sunk) number that tells you what the session has
    already burned, not what the next turn will cost. A 500-turn / 60k
    session is cheap to continue ($0.03/reply); a 40-turn / 350k session
    is expensive ($0.175/reply). Old logic flagged the first and missed
    the second. New logic does the opposite.

    Thresholds map directly to $/reply at Opus cache-read pricing:
        <60k   → <$0.03/reply   → FRESH   (good)    · cheap, keep going
        60–150 → $0.03–0.075    → NORMAL  (hint)    · typical median session
        150–280→ $0.075–0.14    → HANDOFF (warn)    · getting expensive, consider
        280+   → >$0.14/reply   → COMPACT (crit)    · every reply costs real $

    Distribution context from the 7-day study: p50=118k (NORMAL mid),
    p95=424k (deep COMPACT), p99=594k (very deep COMPACT). The bands are
    calibrated so the median session sits comfortably in NORMAL and the
    outliers that actually drive weekly burn are the ones nudged.
    """
    c = context_k or 0
    if c >= 280:
        return "crit", "COMPACT"
    if c >= 150:
        return "warn", "HANDOFF"
    if c >= 60:
        return "hint", "NORMAL"
    return "good", "FRESH"


def _short_project_label(cwd):
    """
    Shorten a project cwd to a terse widget-friendly label. Strips the
    user's home directory so `/Users/alice/code/my-repo` becomes
    `code/my-repo`, then keeps the last two path segments.
    """
    if not cwd:
        return None
    label = cwd
    home = str(Path.home())
    if label.startswith(home + "/"):
        label = label[len(home) + 1:]
    parts = [p for p in label.split("/") if p]
    if len(parts) > 2:
        label = "/".join(parts[-2:])
    elif parts:
        label = parts[-1]
    return label or None


def _scan_session_file(path):
    """Count assistant turns + harvest last context size from a session JSONL.

    Returns {session_id, project, turns, context_tokens, context_k, model}
    or None if the file has no assistant messages.

    "Turns"     = assistant messages (not raw lines — user events don't count).
    "Context"   = the LAST assistant message's total prompt size
                  (cache_read + cache_creation + fresh input) — the number
                  that'll be re-sent on the next turn.
    """
    turns = 0
    last_ctx = None
    last_model = None
    project_cwd = None
    session_id = None
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                # Cheap pre-filter: skip any line that can't be an assistant
                # event. Avoids json.loads() on every user/tool_result line.
                if b'"type":"assistant"' not in raw:
                    if project_cwd is None and b'"cwd"' in raw:
                        try:
                            obj = json.loads(raw.decode("utf-8", errors="replace"))
                            project_cwd = obj.get("cwd")
                            session_id = session_id or obj.get("sessionId")
                        except Exception:
                            pass
                    continue
                try:
                    obj = json.loads(raw.decode("utf-8", errors="replace"))
                except Exception:
                    continue
                if obj.get("type") != "assistant":
                    continue
                # Sidechain (Task subagent) turns don't count toward the
                # user-facing "my session is long" feeling.
                if obj.get("isSidechain"):
                    continue
                turns += 1
                msg = obj.get("message") or {}
                usage = msg.get("usage") or {}
                ctx = (
                    (usage.get("cache_read_input_tokens") or 0)
                    + (usage.get("cache_creation_input_tokens") or 0)
                    + (usage.get("input_tokens") or 0)
                )
                if ctx > 0:
                    last_ctx = ctx
                model = msg.get("model")
                if model:
                    last_model = model
                if project_cwd is None:
                    project_cwd = obj.get("cwd")
                if session_id is None:
                    session_id = obj.get("sessionId")
    except OSError:
        return None

    if turns == 0:
        return None

    return {
        "session_id": session_id or path.stem,
        "project": _short_project_label(project_cwd),
        "project_cwd": project_cwd,
        "turns": turns,
        "context_tokens": last_ctx,
        "context_k": round(last_ctx / 1000, 1) if last_ctx else None,
        "cost_per_reply_usd": round(_cost_per_reply_usd(last_ctx), 4),
        "model": last_model,
    }


def _live_claude_project_dirs():
    """Return {project_dir_name: live_process_count} for every project where
    a `claude` CLI process is currently running.

    Used to filter out "ghost sessions" — JSONL files whose mtime is still
    within the activity window because the file was last touched a few
    minutes ago, but whose owning Claude Code window has since been ctrl-c'd
    or closed. Without this check, closing a Claude Code window leaves its
    transcript flagged as "live" for the full 20-minute mtime window.

    Mechanism:
      1. `ps -axo pid,comm` → find PIDs whose comm is exactly "claude".
         (pgrep is unreliable here — the claude binary rewrites its argv[0]
         to the version string "2.1.101" shortly after launch, so pgrep
         matches inconsistently. The p_comm field stays as "claude" though,
         so ps -o comm is the stable signal.)
      2. `lsof -a -p PID,... -d cwd -Fn` → cwd for each live PID in one call.
      3. Encode each cwd to its ~/.claude/projects/ subdir name by replacing
         both "/" and "_" with "-" (Claude Code's encoding rule).

    Returns an empty dict if `ps` or `lsof` fail — in which case the caller
    falls back to pure mtime-based filtering (old behavior).
    """
    try:
        ps_out = subprocess.run(
            ["ps", "-axo", "pid=,comm="],
            capture_output=True, text=True, timeout=3,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return {}

    pids = []
    for line in ps_out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[1] == "claude":
            pids.append(parts[0])

    if not pids:
        return {}

    try:
        lsof_out = subprocess.run(
            ["lsof", "-a", "-p", ",".join(pids), "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=3,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return {}

    dirs = {}
    # -Fn output is one field per line with a single-char type prefix:
    #   pPID / fcwd / nPATH. We only want the n-lines that are absolute paths.
    for line in lsof_out.splitlines():
        if line.startswith("n/"):
            cwd = line[1:]
            encoded = cwd.replace("/", "-").replace("_", "-")
            dirs[encoded] = dirs.get(encoded, 0) + 1
    return dirs


def live_session_stats(window_min=20, max_sessions=5, path_override=None):
    """Return a list of currently-active Claude Code sessions, worst→best.

    "Active" = a `claude` CLI process is running with its cwd = the JSONL's
    owning project dir, AND the JSONL's mtime is within the last `window_min`
    minutes. The process-liveness check kills "ghost sessions" that got
    ctrl-c'd but still have a fresh mtime. If `ps` / `lsof` fail, we fall
    back to pure mtime filtering (old behavior).

    When N claude processes are running in the same project dir (two
    windows open in the same repo), we keep the N most-recently-mtimed
    JSONLs from that dir — one transcript per live process.

    Sorted by:
        1) band severity (crit > warn > hint > good)
        2) bloat score within band (turns + context_k) — worst first

    `path_override` (for hook use): if given, scan ONLY this specific JSONL
    file regardless of mtime or process liveness. Used by the
    UserPromptSubmit hook which knows its own transcript_path.
    """
    import time

    now = time.time()

    if path_override:
        stats = _scan_session_file(Path(path_override))
        if not stats:
            return []
        band, word = _classify_session(stats["turns"], stats.get("context_k"))
        stats["band"] = band
        stats["status_word"] = word
        stats["bloat_score"] = (stats["turns"] or 0) + (stats.get("context_k") or 0)
        try:
            stats["last_activity_sec"] = int(now - Path(path_override).stat().st_mtime)
        except OSError:
            stats["last_activity_sec"] = None
        return [stats]

    cutoff = now - window_min * 60
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return []

    live_project_counts = _live_claude_project_dirs()

    # Group candidate JSONLs by project dir, then take top-N per dir where
    # N is the live process count for that dir (so two concurrent windows in
    # the same repo both get represented). If live_project_counts is empty
    # (ps/lsof failed), we skip this filter entirely and keep all mtime-fresh
    # JSONLs — same as the old behavior.
    by_project = {}
    for f in projects_dir.glob("*/*.jsonl"):
        if live_project_counts and f.parent.name not in live_project_counts:
            continue  # ghost — no claude process has that cwd
        try:
            mt = f.stat().st_mtime
        except OSError:
            continue
        if mt < cutoff:
            continue
        by_project.setdefault(f.parent.name, []).append((mt, f))

    candidates = []
    for proj, files in by_project.items():
        files.sort(key=lambda x: -x[0])  # newest mtime first
        keep = live_project_counts.get(proj, len(files)) if live_project_counts else len(files)
        candidates.extend(files[:keep])

    if not candidates:
        return []

    results = []
    for mtime, path in candidates:
        stats = _scan_session_file(path)
        if not stats:
            continue
        band, word = _classify_session(stats["turns"], stats.get("context_k"))
        stats["band"] = band
        stats["status_word"] = word
        stats["bloat_score"] = (stats["turns"] or 0) + (stats.get("context_k") or 0)
        stats["last_activity_sec"] = int(now - mtime)
        results.append(stats)

    # Sort: band severity first (crit at top), then highest bloat score.
    results.sort(key=lambda s: (_BAND_ORDER[s["band"]], -s["bloat_score"]))

    return results[:max_sessions]


# Back-compat shim (kept in case anything else calls the old name).
def _live_session_stats(window_min=15):
    ls = live_session_stats(window_min=window_min, max_sessions=1)
    return ls[0] if ls else None


# ---------- backfill throttle ----------
#
# Multiple processes can try to run the JSONL backfill simultaneously:
# the 15-min launchd agent, the widget's 60-s render loop, and an
# interactive `cc-usage` invocation from the shell. SQLite's 30-second
# busy_timeout handles brief contention but a full backfill holds the
# write lock long enough for stampedes to deadlock each other.
#
# Fix: a mtime-based lockfile at data/.backfill.lock. Any caller that
# wants to trigger a backfill first tries _acquire_backfill_lock(max_age);
# a fresh lockfile (mtime newer than max_age seconds) means "someone
# else just did this / is doing this — skip", and we return False. On
# success we touch the lockfile and return True, so the lock is
# effectively held until max_age seconds from now even if the caller
# crashes. That's intentional — we'd rather skip an extra backfill than
# pile up concurrent ones.

def _acquire_backfill_lock(max_age_sec=90):
    """Return True if the caller should run a backfill, False otherwise.

    Checks the lockfile's mtime; if it's older than max_age_sec (or the
    lockfile doesn't exist), touches it to claim the slot and returns
    True. If the lockfile is fresher, someone else just ran (or is
    currently running) a backfill and the caller should skip.
    """
    import time as _time
    lock_path = Path(__file__).resolve().parent / "data" / ".backfill.lock"
    now = _time.time()
    try:
        mtime = lock_path.stat().st_mtime
        if now - mtime < max_age_sec:
            return False
    except FileNotFoundError:
        pass
    except OSError:
        # If we can't stat the lock for any other reason, err on the
        # side of letting one backfill through — worse to silently stall
        # forever than to run a spurious backfill.
        pass
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()
    except OSError:
        pass
    return True


# ---------- live extrapolation ----------
#
# Problem: /api/oauth/usage rate-limits us for hours at a time (429 with
# Retry-After: 0 and no meaningful retry hint). When that happens, the
# launchd poller can't write new snapshots and the widget would otherwise
# freeze on a multi-hour-old reading. The CLAUDE.md widget policy is
# "never paint a red error splash", but that used to silently degrade to
# "never paint fresh numbers" whenever Anthropic locked us out.
#
# Fix: keep the last successful snapshot as a calibration anchor and
# extrapolate forward using local token burn from the `turns` table.
# Anthropic reports quota utilization in whole %, so any small interval
# has 0.5% rounding noise — but aggregated across the current window it
# fits a stable Δ% = k × Δ(tokens / 1M) ratio (confirmed empirically).
#
# Session windows reset every 5h: when the anchor's reset_at has passed
# we roll forward into the new window (anchor% = 0, starting at the old
# reset boundary) and only count tokens from that boundary. Multi-window
# rollovers are handled by walking forward one window at a time.
#
# Result: the widget paints fresh-to-this-minute numbers that close the
# gap between "last snapshot we could pull" and "right now", with zero
# network dependency. The API snapshot remains the source of truth;
# extrapolation is a forward projection from it.

def _bucket_reset(iso_ts):
    """Normalize an Anthropic reset_at timestamp to its hour.

    Anthropic stamps /api/oauth/usage resets with sub-second jitter even
    when the logical window hasn't changed (`...T13:00:00.452766+00:00` vs
    `...T13:00:00.518053+00:00`). Bucketing to `YYYY-MM-DDTHH` gives us a
    stable grouping key so snapshots within the same weekly/session
    window can be treated as comparable.
    """
    if not iso_ts:
        return None
    return iso_ts[:13]


def _empirical_pct_per_mtok(conn, kind, account="primary"):
    """Empirical %-per-Mtok conversion for the current window.

    kind: "session" (five_hour) or "week" (seven_day).
    account: which account's snapshots+turns to use.

    Returns `(last_pct - first_pct) / Σ Mtok(first_ts..last_ts)` across the
    most recent snapshot window. Full-span aggregate is deliberate: any
    pair-wise aggregation that drops intervals with dp==0 inflates the
    ratio, because Anthropic reports utilization rounded to whole % — those
    flat intervals still consumed tokens, so dropping them discards real
    denominator mass and overstates pct/Mtok.

    If the current window has fewer than 2 snapshots, falls back to the
    previous window. Returns None when no window has a usable pair —
    callers MUST skip extrapolation in that case rather than guess.
    """
    pct_col, reset_col = {
        "session": ("five_hour_pct", "five_hour_reset"),
        "week":    ("seven_day_pct", "seven_day_reset"),
    }[kind]

    rows = conn.execute(
        f"SELECT ts, {pct_col} AS pct, {reset_col} AS reset "
        f"FROM snapshots WHERE {pct_col} IS NOT NULL "
        f"AND COALESCE(account, 'primary') = ? "
        f"ORDER BY ts DESC LIMIT 2000",
        (account,),
    ).fetchall()
    if len(rows) < 2:
        return None

    # Group newest→oldest by normalized reset bucket. A new group starts
    # whenever the bucket key changes, so groups[0] is the current window,
    # groups[1] is the window before, etc.
    groups = []
    cur_bucket = object()  # sentinel — never matches a real bucket
    for r in rows:
        b = _bucket_reset(r["reset"])
        if b != cur_bucket:
            groups.append([])
            cur_bucket = b
        groups[-1].append(r)

    for grp in groups:
        if len(grp) < 2:
            continue
        # grp is newest→oldest within one window; first = oldest, last = newest
        first, last = grp[-1], grp[0]
        dp = (last["pct"] or 0) - (first["pct"] or 0)
        if dp <= 0:
            continue  # window reset or flat — no usable signal this pass
        tok_row = conn.execute(
            "SELECT SUM(input_tokens + output_tokens + cache_creation_input_tokens) AS t "
            "FROM turns WHERE ts > ? AND ts <= ? AND COALESCE(account, 'primary') = ?",
            (first["ts"], last["ts"], account),
        ).fetchone()
        tokens = tok_row["t"] or 0
        if tokens <= 0:
            continue
        mtok = tokens / 1_000_000
        return dp / mtok
    return None


def _tokens_since(conn, since_iso, account="primary"):
    """Quota-counted tokens (input + output + cache_creation) since ts."""
    row = conn.execute(
        "SELECT SUM(input_tokens + output_tokens + cache_creation_input_tokens) AS t "
        "FROM turns WHERE ts > ? AND COALESCE(account, 'primary') = ?",
        (since_iso, account),
    ).fetchone()
    return row["t"] or 0


def _roll_window_forward(anchor_pct, anchor_ts_iso, reset_iso, window_hours):
    """Fast-forward past any window boundaries between anchor and now.

    If the anchor snapshot's window has ended, the current window starts
    at the old reset time (anchor% = 0) and ends one window_hours later.
    If many windows have elapsed (session = 5h, so 3+ can fit in a 15h
    gap), walk forward until the reset is in the future.

    Returns (effective_anchor_pct, effective_anchor_ts, effective_reset_iso).
    When the window hasn't rolled, returns the inputs unchanged.
    """
    reset_dt = _parse_iso(reset_iso)
    now = datetime.now(timezone.utc)
    if not reset_dt or now < reset_dt:
        return anchor_pct, anchor_ts_iso, reset_iso
    while now >= reset_dt:
        reset_dt = reset_dt + timedelta(hours=window_hours)
    new_window_start_dt = reset_dt - timedelta(hours=window_hours)
    return 0.0, new_window_start_dt.isoformat(), reset_dt.isoformat()


def _extrapolate_live(conn, data, anchor_ts_iso, account="primary"):
    """Advance a raw /api/oauth/usage dict to reflect live token burn.

    `data` is the last snapshot's raw payload — possibly seconds old,
    possibly hours old. We advance `five_hour.utilization` and
    `seven_day.utilization` using the empirical pct-per-Mtok ratio and
    the turns table, so the widget paints a reading that's current to
    this minute even when the background API poll is being rate-limited.

    Side effects on `data`:
      - `five_hour.utilization` and `seven_day.utilization` bumped by the
        extrapolated delta (clipped to [0, 100]).
      - `five_hour.resets_at` / `seven_day.resets_at` advanced when the
        anchor's window has rolled.
      - `_extrapolated` diagnostic block added so downstream code can
        surface freshness metadata.
    """
    info = {
        "anchor_ts": anchor_ts_iso,
        "anchor_age_sec": None,
        "session": {"applied": False},
        "week":    {"applied": False},
    }
    anchor_dt = _parse_iso(anchor_ts_iso)
    if anchor_dt:
        info["anchor_age_sec"] = int(
            (datetime.now(timezone.utc) - anchor_dt).total_seconds()
        )

    def _apply(kind, block_key, window_hours):
        block = data.get(block_key) or {}
        if block.get("resets_at") is None or block.get("utilization") is None:
            return
        k = _empirical_pct_per_mtok(conn, kind, account=account)
        if not k or k <= 0:
            return
        eff_pct, eff_ts, eff_reset = _roll_window_forward(
            block.get("utilization") or 0,
            anchor_ts_iso,
            block.get("resets_at"),
            window_hours=window_hours,
        )
        tokens = _tokens_since(conn, eff_ts, account=account)
        delta_pct = (tokens / 1_000_000) * k
        new_pct = min(100.0, max(0.0, eff_pct + delta_pct))
        data[block_key]["utilization"] = new_pct
        data[block_key]["resets_at"] = eff_reset
        info[kind] = {
            "applied": True,
            "anchor_pct": round(eff_pct, 2),
            "delta_pct": round(delta_pct, 2),
            "tokens": tokens,
            "pct_per_mtok": round(k, 4),
            "rolled_over": eff_ts != anchor_ts_iso,
        }

    _apply("session", "five_hour", 5)
    _apply("week",    "seven_day", 168)

    data["_extrapolated"] = info
    return data


# ---------- widget payload ----------

def widget_payload(data=None, conn=None, target=DEFAULT_TARGET, account="primary"):
    """
    Return a compact dict of the stats the desktop widget renders.
    No side effects (no snapshot insert): this is called from launchd +
    an Übersicht widget, which refresh on their own cadence.
    """
    if data is None:
        data = get_usage()
    if conn is None:
        conn = dbmod.connect()
    # SQL fragment for filtering turns/snapshots by account. Used by every
    # query below so we don't pollute one account's stats with another's.
    _acct_where = "AND COALESCE(account, 'primary') = ?"
    _acct_bind = (account,)

    def _bucket(block, want_active=False):
        if not block:
            return None
        used = block.get("utilization", 0) or 0
        reset_iso = block.get("resets_at")
        hours_left = _hours_until(reset_iso) if reset_iso else 0
        out = {
            "used_pct": round(used, 2),
            "remaining_pct": round(100 - used, 2),
            "reset_iso": reset_iso,
            "reset_label": _fmt_reset(reset_iso) if reset_iso else None,
            "hours_left": round(hours_left, 2),
        }
        if want_active and reset_iso:
            sess_start = _session_start_iso(reset_iso)
            if sess_start:
                s = _active_hour_stats(conn, sess_start, account=account)
                if s["active_hours"] >= 1 and used > 0:
                    rate = used / s["active_hours"]
                    out["active_hours"] = s["active_hours"]
                    out["rate_pct_per_active_hour"] = round(rate, 2)
                    out["headroom_active_hours"] = round((100 - used) / rate, 2) if rate > 0 else None
                # Short local-time strings for the widget ("4:28pm" / "9:28pm")
                # so the widget can display WHEN the 5h window started + ends.
                sstart_dt = _parse_iso(sess_start)
                rs_dt = _parse_iso(reset_iso)
                if sstart_dt:
                    out["started_at_local"] = sstart_dt.astimezone(PT).strftime("%-I:%M%p").lower()
                if rs_dt:
                    out["reset_time_local"] = rs_dt.astimezone(PT).strftime("%-I:%M%p").lower()
        # Short reset time for non-session buckets too — weekly reset "6:00am Fri"
        if not want_active and reset_iso:
            rs_dt = _parse_iso(reset_iso)
            if rs_dt:
                out["reset_time_local"] = rs_dt.astimezone(PT).strftime("%-I:%M%p %a").lower()
        return out

    session = _bucket(data.get("five_hour"), want_active=True)
    weekly = _bucket(data.get("seven_day"))
    weekly_sonnet = _bucket(data.get("seven_day_sonnet"))
    weekly_opus = _bucket(data.get("seven_day_opus"))

    # Weekly pacing: where SHOULD we be vs where we ARE (linear baseline)
    if weekly and weekly.get("reset_iso") and weekly["hours_left"] > 0:
        hours_elapsed = max(0.0, 168 - weekly["hours_left"])
        if hours_elapsed > 0:
            ideal_now = (hours_elapsed / 168) * target
            # 2 decimals: ideal_pct creeps up ~0.01%/min, so at the widget's
            # 60s refresh cadence 2 decimals are the lowest-order digit that
            # actually moves between polls. Any more is just visual noise.
            weekly["ideal_pct"] = round(ideal_now, 2)
            weekly["vs_ideal_pct"] = round(weekly["used_pct"] - ideal_now, 2)
            # Linear projection: if you kept this pace through the whole week,
            # what % would you land at? >target means overshoot, <target undershoot.
            weekly["projected_pct"] = round(
                weekly["used_pct"] * (168 / hours_elapsed), 1
            )
            week_start = _week_start_iso(weekly["reset_iso"])
            if week_start:
                ws = _active_hour_stats(conn, week_start, account=account)
                if ws["active_hours"] >= 1:
                    weekly["active_hours"] = ws["active_hours"]
        # Days left until weekly reset (for forecast math)
        weekly["days_left"] = round(weekly["hours_left"] / 24, 2)

    # Weekly per-day breakdown — bucket by local calendar day since weekly reset,
    # so the widget shows Mon/Tue/Wed/... with active hours + approximate % share.
    # Claude's quota API doesn't expose per-day %, so we approximate pct_share
    # by token contribution: day_tokens / week_tokens × weekly.used_pct. It's
    # a proxy, but good enough to see which days were heavy.
    if weekly and weekly.get("reset_iso"):
        week_start = _week_start_iso(weekly["reset_iso"])
        if week_start:
            rows = conn.execute(
                f"""
                SELECT ts, input_tokens, output_tokens, cache_creation_input_tokens
                FROM turns
                WHERE ts >= ? AND is_sidechain = 0 {_acct_where}
                """,
                (week_start,) + _acct_bind,
            ).fetchall()
            by_date = {}
            for r in rows:
                dt = _parse_iso(r["ts"])
                if not dt:
                    continue
                pt_dt = dt.astimezone(PT)
                key = pt_dt.strftime("%Y-%m-%d")
                entry = by_date.setdefault(
                    key, {"hours": set(), "turns": 0, "tokens": 0}
                )
                entry["hours"].add(pt_dt.strftime("%H"))
                entry["turns"] += 1
                entry["tokens"] += (
                    (r["input_tokens"] or 0)
                    + (r["output_tokens"] or 0)
                    + (r["cache_creation_input_tokens"] or 0)
                )
            total_tokens = sum(d["tokens"] for d in by_date.values()) or 0
            ws_pt_date = _parse_iso(week_start).astimezone(PT).date()
            rs_pt_date = _parse_iso(weekly["reset_iso"]).astimezone(PT).date()
            today_pt_date = datetime.now(timezone.utc).astimezone(PT).date()
            by_day = []
            cur_date = ws_pt_date
            while cur_date <= rs_pt_date:
                key = cur_date.strftime("%Y-%m-%d")
                dd = by_date.get(key, {"hours": set(), "turns": 0, "tokens": 0})
                token_share = (dd["tokens"] / total_tokens) if total_tokens else 0
                pct_share = round(
                    token_share * (weekly.get("used_pct") or 0), 1
                )
                by_day.append(
                    {
                        "dow": cur_date.strftime("%a"),
                        "date": key,
                        "active_hours": len(dd["hours"]),
                        "turns": dd["turns"],
                        "tokens_m": round(dd["tokens"] / 1_000_000, 2),
                        "pct_share": pct_share,
                        "is_today": cur_date == today_pt_date,
                        "is_future": cur_date > today_pt_date,
                    }
                )
                cur_date += timedelta(days=1)
            weekly["by_day"] = by_day

    # "Today" stats — bucketed in local TZ so a day = the user's actual workday, not UTC
    pt_now = datetime.now(timezone.utc).astimezone(PT)
    pt_midnight = pt_now.replace(hour=0, minute=0, second=0, microsecond=0)
    pt_midnight_utc_iso = pt_midnight.astimezone(timezone.utc).isoformat()
    today_row = conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT strftime('%Y-%m-%d %H', ts)) AS active_hours,
            COUNT(*) AS turns,
            COUNT(DISTINCT session_id) AS sessions,
            SUM(input_tokens + output_tokens + cache_creation_input_tokens) AS tokens
        FROM turns
        WHERE ts >= ? AND is_sidechain = 0 {_acct_where}
        """,
        (pt_midnight_utc_iso,) + _acct_bind,
    ).fetchone()
    top_model_row = conn.execute(
        f"""
        SELECT model, SUM(input_tokens + output_tokens + cache_creation_input_tokens) AS tok
        FROM turns
        WHERE ts >= ? AND is_sidechain = 0 AND model IS NOT NULL {_acct_where}
        GROUP BY model ORDER BY tok DESC LIMIT 1
        """,
        (pt_midnight_utc_iso,) + _acct_bind,
    ).fetchone()
    top_project_row = conn.execute(
        f"""
        SELECT project_cwd, SUM(input_tokens + output_tokens + cache_creation_input_tokens) AS tok
        FROM turns
        WHERE ts >= ? AND is_sidechain = 0 AND project_cwd IS NOT NULL {_acct_where}
        GROUP BY project_cwd ORDER BY tok DESC LIMIT 1
        """,
        (pt_midnight_utc_iso,) + _acct_bind,
    ).fetchone()

    def _short_model(m):
        if not m:
            return None
        # "claude-opus-4-6" → "opus", "claude-sonnet-4-6" → "sonnet"
        for tag in ("opus", "sonnet", "haiku"):
            if tag in m:
                return tag
        return m

    def _short_project(p):
        if not p:
            return None
        return p.rstrip("/").split("/")[-1]

    today = {
        "active_hours": (today_row["active_hours"] or 0) if today_row else 0,
        "turns": (today_row["turns"] or 0) if today_row else 0,
        "sessions": (today_row["sessions"] or 0) if today_row else 0,
        "tokens_m": round(((today_row["tokens"] or 0) if today_row else 0) / 1_000_000, 1),
        "top_model": _short_model(top_model_row["model"]) if top_model_row else None,
        "top_project": _short_project(top_project_row["project_cwd"]) if top_project_row else None,
    }

    # Weekly pull-back plan + constraint
    plan = None
    constraint_label = None
    constraint_safe = None
    buckets_for_constraint = [
        ("Weekly — all models", weekly),
        ("Weekly — Sonnet only", weekly_sonnet),
        ("Weekly — Opus only", weekly_opus),
    ]
    for lbl, b in buckets_for_constraint:
        if not b or not b.get("reset_iso") or b["hours_left"] <= 0:
            continue
        days_left = b["hours_left"] / 24
        safe_per_day = max(0.0, (target - b["used_pct"]) / days_left) if days_left > 0 else 0
        if constraint_safe is None or safe_per_day < constraint_safe:
            constraint_safe = safe_per_day
            constraint_label = lbl
            # compute tomorrow hours against THIS bucket's pacing
            week_start = _week_start_iso(b["reset_iso"])
            if week_start:
                stats = _active_hour_stats(conn, week_start, account=account)
                if stats["active_hours"] >= 2:
                    plan = _pull_back_plan(
                        current_pct=b["used_pct"],
                        target_pct=target,
                        hours_left=b["hours_left"],
                        active_hours_so_far=stats["active_hours"],
                    )
                    if plan:
                        plan["active_hours_so_far"] = stats["active_hours"]
                        plan["turns"] = stats["turns"]

    tomorrow_hours = round(plan["daily_hours"], 2) if plan else None
    daily_budget_pct = round(plan["daily_budget_pct"], 2) if plan else None
    rate_pct_per_hour = round(plan["rate_pct_per_hour"], 2) if plan else None

    # Pacing status label for the weekly constraint
    if plan:
        if plan["daily_hours"] >= 8:
            status = "plenty of headroom"
        elif plan["daily_hours"] >= 4:
            status = "steady"
        elif plan["daily_hours"] >= 2:
            status = "pull back"
        else:
            status = "PULL BACK HARD"
    else:
        status = "—"

    extra = data.get("extra_usage") or {}
    extra_payload = None
    if extra.get("is_enabled"):
        used_cents = extra.get("used_credits") or 0
        used_dollars = used_cents / 100
        cap_dollars = (extra.get("monthly_limit") or 0) / 100
        remaining_dollars = max(0.0, cap_dollars - used_dollars)
        reset_iso = extra.get("resets_at")

        # Project forward: at observed daily burn, when does the monthly
        # cap hit? The API doesn't return a `resets_at` for extra_usage,
        # so we infer the monthly cycle boundary from snapshot history
        # (a reset shows up as the counter dropping between adjacent rows).
        # Noisy with <24h of data or a flat counter; the JSX labels it
        # as "tracking" when pace_lookback_hours is short.
        pace_info = _dollar_pace_since_last_reset(conn, used_cents)
        pace_per_day = None
        pace_lookback_hours = None
        pace_delta_dollars = None
        cap_hit_iso = None
        cap_hit_label = None
        days_until_cap = None
        will_exhaust_before_reset = False
        if pace_info:
            pace_per_day, pace_lookback_hours, pace_delta_dollars = pace_info
            # Only project a date if the counter has actually moved. A flat
            # counter (delta=0) means "you haven't burned any overage in the
            # lookback window" — don't project a misleading "never" date.
            if pace_per_day > 0 and remaining_dollars > 0:
                days_until_cap = remaining_dollars / pace_per_day
                cap_hit_dt = datetime.now(timezone.utc) + timedelta(days=days_until_cap)
                cap_hit_iso = cap_hit_dt.isoformat()
                cap_hit_label = _fmt_reset(cap_hit_iso)
                if reset_iso:
                    hours_to_reset = _hours_until(reset_iso)
                    if hours_to_reset is not None:
                        days_to_reset = hours_to_reset / 24
                        will_exhaust_before_reset = days_until_cap < days_to_reset

        extra_payload = {
            "used_pct": round(extra.get("utilization", 0) or 0, 2),
            "used_dollars": round(used_dollars, 2),
            "cap_dollars": round(cap_dollars, 2),
            "remaining_dollars": round(remaining_dollars, 2),
            "reset_iso": reset_iso,
            "reset_label": _fmt_reset(reset_iso) if reset_iso else None,
            "pace_dollars_per_day": round(pace_per_day, 2) if pace_per_day is not None else None,
            "pace_lookback_hours": round(pace_lookback_hours, 1) if pace_lookback_hours is not None else None,
            "pace_delta_dollars": round(pace_delta_dollars, 2) if pace_delta_dollars is not None else None,
            "days_until_cap": round(days_until_cap, 2) if days_until_cap is not None else None,
            "cap_hit_iso": cap_hit_iso,
            "cap_hit_label": cap_hit_label,
            "will_exhaust_before_reset": will_exhaust_before_reset,
        }

    acct_cfg = ACCOUNTS.get(account, {})
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_pt": datetime.now(timezone.utc).astimezone(PT).strftime("%-I:%M%p").lower(),
        "target_pct": target,
        "account_id": account,
        "account_label": acct_cfg.get("label", account),
        "account_tier": acct_cfg.get("tier", "unknown"),
        "session": session,
        "weekly": weekly,
        "weekly_sonnet": weekly_sonnet,
        "weekly_opus": weekly_opus,
        "today": today,
        "live_sessions": live_session_stats(window_min=20, max_sessions=5),
        "extra": extra_payload,
        "constraint": {
            "label": constraint_label,
            "safe_pct_per_day": round(constraint_safe, 2) if constraint_safe is not None else None,
            "daily_budget_pct": daily_budget_pct,
            "tomorrow_active_hours": tomorrow_hours,
            "rate_pct_per_active_hour": rate_pct_per_hour,
            "status": status,
        },
        # Forward the extrapolation diagnostic block so the widget can show
        # "live (api stale 4h)" instead of silently freezing. Absent when the
        # caller didn't run extrapolation (e.g. CLI --json-raw path).
        "extrapolated": data.get("_extrapolated"),
    }


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(
        description="Claude Code usage dashboard with pacing, charts, search, and validation.",
    )
    ap.add_argument("--json", action="store_true", help="dump raw API JSON")
    ap.add_argument("--widget-json", action="store_true", help="compact computed JSON for the desktop widget")
    ap.add_argument("--plain", action="store_true", help="skip recording a snapshot")
    ap.add_argument("--report", action="store_true", help="include per-session breakdown since weekly reset")
    ap.add_argument("--charts", action="store_true", help="include hourly + daily ASCII burn charts")
    ap.add_argument("--search", metavar="SUBSTR", help="filter by project_cwd substring + show matches")
    ap.add_argument("--validate", action="store_true", help="Max plan drift check: Δ quota%% vs token burn")
    ap.add_argument("--target", type=float, default=DEFAULT_TARGET, help="weekly target %% (default 99)")
    ap.add_argument(
        "--snapshot-only", action="store_true",
        help="record one snapshot silently and exit (for launchd)",
    )
    ap.add_argument(
        "--source", default="cli",
        help="source tag on the snapshot row (cli | launchd | hook)",
    )
    args = ap.parse_args()

    if args.json:
        print(json.dumps(get_usage(), indent=2))
        return 0

    try:
        conn = dbmod.connect()
    except Exception:
        if args.widget_json or args.snapshot_only:
            # Widget / launchd must never crash to stderr.
            print("{}" if args.widget_json else "", end="")
            return 0
        raise

    if args.widget_json:
        # Strategy: never let the widget paint stale numbers. The
        # /api/oauth/usage endpoint rate-limits us for hours at a time
        # (429 with Retry-After: 0), so we can't count on a live fetch
        # every render. Instead:
        #
        #   1. Use the most recent snapshot as a calibration anchor.
        #   2. Quick incremental backfill so the turns table has every
        #      assistant turn up to this second.
        #   3. Extrapolate session% and week% forward from the anchor
        #      using local token burn × empirical %-per-Mtok.
        #
        # That keeps the widget's numbers live-to-the-minute with zero
        # network dependency. The API snapshot stays the source of truth
        # — extrapolation is a forward projection from it, and each new
        # successful launchd snapshot re-anchors us automatically.
        #
        # Multi-account: loop over ACCOUNTS, build a per-account payload,
        # wrap in {"accounts": {...}, "updated_at": ..., "updated_pt": ...}.
        #
        # Error policy per CLAUDE.md: the widget must NEVER render a red
        # error. If we have no anchor AND the one emergency live fetch
        # fails for ALL accounts, print `{}` so the JSX shows "loading…"
        # and tries again on its next 60s refresh.

        # Keep the turns table fresh enough for extrapolation to matter.
        # (One backfill pass covers both accounts — both glob sets.)
        try:
            newest_row = conn.execute(
                "SELECT MAX(ts) AS m FROM turns"
            ).fetchone()
            newest = newest_row["m"] if newest_row else None
            newest_dt = _parse_iso(newest) if newest else None
            stale_turns = (
                newest_dt is None
                or (datetime.now(timezone.utc) - newest_dt).total_seconds() > 120
            )
        except Exception:
            stale_turns = True
        if stale_turns and _acquire_backfill_lock(max_age_sec=90):
            try:
                subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).parent / "claude_usage_backfill.py"),
                        "--since", "10m",
                    ],
                    capture_output=True, text=True, timeout=20,
                )
            except (subprocess.SubprocessError, OSError):
                pass

        accounts_payload = {}
        for acct_id, acct_cfg in ACCOUNTS.items():
            row = dbmod.latest_snapshot(conn, account=acct_id)
            data = None
            anchor_ts = None
            if row and row["raw_json"]:
                try:
                    data = json.loads(row["raw_json"])
                    anchor_ts = row["ts"]
                except Exception:
                    data = None

            if data is None:
                # Cold start for this account — try one live fetch.
                try:
                    data = get_usage(keychain_service=acct_cfg["keychain"])
                    anchor_ts = datetime.now(timezone.utc).isoformat()
                    dbmod.insert_snapshot(
                        conn, ts=anchor_ts, source="widget", data=data,
                        account=acct_id,
                    )
                except Exception:
                    continue  # skip this account, try the next

            try:
                _extrapolate_live(conn, data, anchor_ts, account=acct_id)
                accounts_payload[acct_id] = widget_payload(
                    data=data, conn=conn, target=args.target, account=acct_id,
                )
            except Exception:
                continue  # skip this account — never let a crash reach stderr

        if not accounts_payload:
            print("{}")
            return 0

        # Compute primary→cap ETA: when will the primary account hit 100%
        # weekly? Attach to the overflow payload so the widget can show
        # "switch ~Tue 2pm" on the overflow row.
        pri = accounts_payload.get("primary", {})
        ovf = accounts_payload.get("overflow")
        pri_wk = pri.get("weekly") or {}
        if ovf and pri_wk.get("used_pct") is not None and pri_wk.get("hours_left"):
            used = pri_wk["used_pct"]
            hours_left = pri_wk["hours_left"]
            hours_elapsed = max(0.01, 168 - hours_left)
            if used > 0 and hours_elapsed > 0:
                # Linear projection: at current average pace, how many
                # hours until we hit 100%?
                rate_pct_per_hour = used / hours_elapsed
                remaining_pct = 100.0 - used
                if rate_pct_per_hour > 0 and remaining_pct > 0:
                    hours_to_cap = remaining_pct / rate_pct_per_hour
                    cap_dt = datetime.now(timezone.utc) + timedelta(hours=hours_to_cap)
                    cap_local = cap_dt.astimezone(PT)
                    # "Tue 2pm" style label
                    cap_label = cap_local.strftime("%a %-I:%M%p").lower()
                    ovf["primary_cap_eta"] = {
                        "hours": round(hours_to_cap, 1),
                        "iso": cap_dt.isoformat(),
                        "label": cap_label,
                        "rate_pct_per_hour": round(rate_pct_per_hour, 3),
                        "will_cap": hours_to_cap < hours_left,  # True if cap before weekly reset
                    }
                else:
                    ovf["primary_cap_eta"] = None
            else:
                ovf["primary_cap_eta"] = None

        # ── Bridge mode ──
        # When primary is capped and primary's reset comes BEFORE overflow's
        # own 7-day reset, the overflow only needs to bridge until primary
        # comes back — not last the full week. Re-anchor overflow weekly
        # pacing against primary's reset (shorter horizon → more headroom).
        # The real 7d cycle is preserved under `real_*` for fallback display.
        if ovf and (pri_wk.get("used_pct") or 0) >= 95:
            ovf_wk = ovf.get("weekly") or {}
            pri_reset_iso = pri_wk.get("reset_iso")
            ovf_reset_iso = ovf_wk.get("reset_iso")
            if pri_reset_iso and ovf_reset_iso and pri_reset_iso < ovf_reset_iso:
                try:
                    pri_reset_dt = datetime.fromisoformat(pri_reset_iso.replace("Z", "+00:00"))
                    ovf_reset_dt = datetime.fromisoformat(ovf_reset_iso.replace("Z", "+00:00"))
                    now_utc = datetime.now(timezone.utc)
                    pri_hours_left = max(0.0, (pri_reset_dt - now_utc).total_seconds() / 3600.0)
                    ovf_cycle_start = ovf_reset_dt - timedelta(hours=168)
                    cycle_total_h = max(0.01, (pri_reset_dt - ovf_cycle_start).total_seconds() / 3600.0)
                    elapsed_h = max(0.0, (now_utc - ovf_cycle_start).total_seconds() / 3600.0)
                    ovf_used = float(ovf_wk.get("used_pct") or 0)
                    ovf_remaining = max(0.0, 100.0 - ovf_used)
                    days_left = pri_hours_left / 24.0
                    safe_per_day = (ovf_remaining / days_left) if days_left > 0 else 0.0
                    ideal_pct = (elapsed_h / cycle_total_h) * float(args.target) if cycle_total_h > 0 else None
                    projected_pct = (ovf_used / elapsed_h) * cycle_total_h if elapsed_h > 0 else None
                    pri_reset_pt = pri_reset_dt.astimezone(PT)
                    bridge_label = pri_reset_pt.strftime("%-I%p %a").lower()
                    bridge_time_local = pri_reset_pt.strftime("%-I:%M%p %a").lower()
                    ovf_wk["bridge"] = {
                        "applied": True,
                        "reset_iso": pri_reset_iso,
                        "reset_label": bridge_label,
                        "reset_time_local": bridge_time_local,
                        "hours_left": round(pri_hours_left, 2),
                        "days_left": round(days_left, 2),
                        "remaining_pct": round(ovf_remaining, 2),
                        "safe_pct_per_day": round(safe_per_day, 2),
                        "ideal_pct": round(ideal_pct, 2) if ideal_pct is not None else None,
                        "projected_pct": round(projected_pct, 2) if projected_pct is not None else None,
                        "vs_ideal_pct": round(ovf_used - ideal_pct, 2) if ideal_pct is not None else None,
                        "real_reset_label": ovf_wk.get("reset_label"),
                        "real_reset_time_local": ovf_wk.get("reset_time_local"),
                        "real_days_left": ovf_wk.get("days_left"),
                        "real_hours_left": ovf_wk.get("hours_left"),
                        "real_ideal_pct": ovf_wk.get("ideal_pct"),
                        "real_vs_ideal_pct": ovf_wk.get("vs_ideal_pct"),
                        "real_projected_pct": ovf_wk.get("projected_pct"),
                    }
                except Exception:
                    pass

        print(json.dumps({
            "accounts": accounts_payload,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_pt": datetime.now(timezone.utc).astimezone(PT).strftime("%-I:%M%p").lower(),
        }))
        return 0

    if args.snapshot_only:
        # Silent mode for launchd — no panel, no prints on success.
        # Two independent tasks run here, and each MUST survive the other
        # failing. In particular the backfill is valuable even when the
        # API fetch is being rate-limited (429s for hours at a time are
        # normal), because it keeps the turns table fresh for the widget's
        # live-extrapolation path.
        #
        # Multi-account: loop over ACCOUNTS, fetch + insert for each.
        # Each account's failure is independent — one account's 429
        # doesn't block the other's snapshot.
        api_ok = True
        for acct_id, acct_cfg in ACCOUNTS.items():
            try:
                data = get_usage(keychain_service=acct_cfg["keychain"])
                dbmod.insert_snapshot(
                    conn,
                    ts=datetime.now(timezone.utc).isoformat(),
                    source=args.source,
                    data=data,
                    account=acct_id,
                )
            except Exception as e:
                print(f"snapshot failed ({acct_id}): {e}", file=sys.stderr)
                api_ok = False
        # Respect the backfill lock so we don't stampede the widget's
        # own backfill subprocess. max_age of 60s is generous: launchd
        # runs us every 15 min, so we'll almost always acquire — and if
        # a widget call beat us by <60s, their recent rescan is fresh
        # enough to skip ours this round.
        if _acquire_backfill_lock(max_age_sec=60):
            try:
                subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).parent / "claude_usage_backfill.py"),
                        "--since", "2h",
                    ],
                    capture_output=True, text=True, timeout=120,
                )
            except (subprocess.SubprocessError, OSError) as e:
                print(f"backfill failed (non-fatal): {e}", file=sys.stderr)
        # Exit non-zero if the API half failed so launchd's last-exit-status
        # still reflects real API health (that's what the user sees in
        # `launchctl list com.infrastructure.cc-usage.snapshot`).
        return 0 if api_ok else 1

    # Panel always renders first (unless --validate-only mode)
    print_panel(
        conn=conn,
        record=not args.plain,
        report=args.report,
        charts=args.charts,
        target=args.target,
        project_filter=args.search,
    )

    if args.search:
        _print_search(conn, args.search)

    if args.validate:
        _validate_anthropic(conn)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
