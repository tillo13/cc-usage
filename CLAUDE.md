# cc_usage — internal notes for Claude Code

These are developer notes consumed by Claude Code when editing this repo.
For end-user docs see `README.md`.

## What this is

A self-contained stack that

1. Polls Anthropic's `/api/oauth/usage` endpoint (the same endpoint the
   official Claude Code CLI uses to render its `/status` panel).
2. Backfills per-turn token counts by walking
   `~/.claude/projects/*/*.jsonl` — every assistant message becomes one
   row in the local SQLite DB with input/output/cache token breakdowns,
   tool calls, stop reasons, thinking-vs-visible content, etc.
3. Correlates #1 (authoritative quota %) against #2 (granular token
   burn) so the user can see pacing, per-project cost, per-tool waste,
   and drift against the Anthropic Max plan advertised allotments.
4. Surfaces a tiny subset of all that through a macOS menu-bar widget
   built on Übersicht — the only always-visible "am I going to blow my
   quota this week" readout anywhere.

## Files

- `claude_code_usage.py` — main CLI, `--widget-json` producer, all the
  rendering + pacing + validation logic. Entry points:
    - `cc-usage` — full panel with pacing + charts
    - `cc-usage --widget-json` — compact JSON for the Übersicht widget
    - `cc-usage --snapshot-only` — silent mode for the 15-min launchd agent
    - `cc-usage --validate` — Max plan drift check
- `claude_usage_db.py` — SQLite schema + helpers. Six tables; DB path
  resolves to `data/claude_usage.db` sibling of this file.
- `claude_usage_backfill.py` — idempotent JSONL parser. Walks
  `~/.claude/projects/*/*.jsonl`, upserts rows for snapshots / turns /
  tool_calls / tool_results / user_prompts / events via stable UUID
  keys, so re-runs are free.
- `stats.py` — the fun report. 13 sections of behavioral breakdowns
  against the DB: token burn by day, project leaderboard, tool
  inventory, hourly heatmap, stop_reason distribution, sidechain tax,
  etc.
- `ubersicht/cc-usage.jsx` — the widget. Canonical copy lives here; an
  installed copy must be placed at
  `~/Library/Application Support/Übersicht/widgets/cc-usage.jsx` (copy
  after edits — Übersicht's FSEvents watcher ignores symlink targets).
- `data/claude_usage.db` — SQLite, git-ignored. Contains every per-turn
  token row, session ID, and project path in the user's usage history.
- `launchd/com.cc-usage.snapshot.plist.template` — launchd agent
  template that polls every 15 min. See the README for install.

## Wiring (user-installed, not tracked in repo)

| Consumer | Path |
|---|---|
| Shell alias `cc-usage` | `~/.zshrc` (one line — `alias cc-usage="<python> <repo>/claude_code_usage.py"`) |
| launchd 15-min snapshot | `~/Library/LaunchAgents/com.cc-usage.snapshot.plist` |
| Übersicht widget | `~/Library/Application Support/Übersicht/widgets/cc-usage.jsx` |

All three reference absolute paths chosen by the user at install time.
If the repo is moved, all three must be updated.

## Python interpreter requirement

The widget and the launchd agent BOTH need a Python 3 with:

- `requests` installed
- macOS **Full Disk Access** / Desktop TCC permission granted to the
  interpreter binary (System Settings → Privacy & Security → Full Disk
  Access). Without this, the launchd agent and the widget cannot read
  `~/.claude/projects/*/*.jsonl` and will fail with
  `Operation not permitted`.

The stock `/usr/local/bin/python3` usually fails this check — the
simplest workaround is to point at a virtualenv whose parent directory
has already been granted Full Disk Access (most devs already have a
permitted venv somewhere on their machine).

Timezone for local-time displays is controlled by the `CC_USAGE_TZ` env
var (any IANA zone name). Default is `America/Los_Angeles`.

## Data integrity notes

- OAuth token is **read** from the macOS keychain (`security
  find-generic-password -s "Claude Code-credentials"`). Never written,
  never refreshed — refreshing rotates the token and kicks the live CLI
  back to `/login`, so the script deliberately avoids that path.
- The `anthropic-beta: oauth-2025-04-20` header is required to unlock
  OAuth on `/api/oauth/*` — without it the server returns 401 "OAuth
  authentication is currently not supported".
- Backfill is idempotent via `UNIQUE(message_uuid)` / `UNIQUE(tool_use_id)`
  on each table, so the 2h overlap window run by the launchd agent is
  free.
- Schema migrations are forward-only via `PRAGMA table_info` + in-place
  `ALTER TABLE ADD COLUMN` — safe to call against a stale DB.

## Widget failure policy

The Übersicht widget must **never** paint a red error splash AND must
**never** freeze on stale data. Two things keep both promises true:

1. **No live API call on the render path.** `--widget-json` reads the
   most recent `snapshots` row as a calibration anchor and extrapolates
   session% / week% forward using local token burn × the empirical
   `%-per-Mtoken` ratio (`_empirical_pct_per_mtok` + `_extrapolate_live`
   in `claude_code_usage.py`). Session windows rolling over at the 5h
   boundary are detected and rolled to 0% automatically via
   `_roll_window_forward`.
2. **Backfill stampede prevention.** The widget path also kicks a
   short incremental backfill (`--since 10m`) so the `turns` table has
   the latest JSONL rows before extrapolation runs. Concurrent backfill
   processes would deadlock each other on the SQLite write lock, so
   every caller (widget + launchd agent) must first call
   `_acquire_backfill_lock(max_age_sec=...)` — a mtime-based lockfile
   at `data/.backfill.lock` that ensures at most one backfill is in
   flight at a time and rate-limits restarts.

Error policy: only when there is *no* snapshot row at all (cold start,
brand new DB) does `--widget-json` emit `{}` so the JSX shows
"loading…". Every other path must produce a fresh, numerically
coherent payload — no tracebacks, no live-fetch bypass, no red errors.

This is intentional and documented in the code. Don't add error
surfacing to the widget render path. If you think the widget should
paint an error, you're wrong — extend the extrapolation instead.

The `--snapshot-only` launchd path ALSO must survive API failures
without killing the backfill half. The snapshot insert and the
incremental backfill are independent: an API 429 storm (hours long,
Retry-After: 0, no useful retry hint) must not freeze the turns
table, because the turns table is what keeps the extrapolation alive.
