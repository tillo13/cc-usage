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
- `launchd/com.ubersicht.keepalive.plist.template` — launchd watchdog
  that starts Übersicht at login and restarts it within seconds of
  any crash / Cmd-Q / forced kill. Non-negotiable for the widget to
  qualify as "always-visible." Uses `KeepAlive=true`,
  `ThrottleInterval=10`, `ProcessType=Interactive`.

## Wiring (user-installed, not tracked in repo)

| Consumer | Path |
|---|---|
| Shell alias `cc-usage` | `~/.zshrc` (one line — `alias cc-usage="<python> <repo>/claude_code_usage.py"`) |
| launchd 15-min snapshot | `~/Library/LaunchAgents/com.cc-usage.snapshot.plist` |
| launchd Übersicht watchdog | `~/Library/LaunchAgents/com.ubersicht.keepalive.plist` |
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

## Account tiers (post-SpaceX, as of 2026-05-30)

Primary (`claude`) is **Max 20x**. Overflow (`claude2` / `~/.claude-alt`)
**downgraded Max 20x → Pro on 2026-05-15, as scheduled** — the downgrade
*executed* (confirmed 2026-05-30: 239 overflow turns hit 99% of the 5h
session while 901 primary turns sat at ~4%, i.e. overflow's ceiling is
~1/20th — Pro, not Max). The `ACCOUNTS` config in `claude_code_usage.py`
now reflects this (`overflow` → `label: "Pro", tier: "pro"`); the API
exposes no tier field, so that config is the source of truth.

**The scarcity premise this tool was built on is largely gone.** On
2026-05-06 Anthropic signed a SpaceX compute deal (300+ MW, 220k+ GPUs)
and **doubled the 5-hour Claude Code limits + removed peak-hour
throttling**; ~2026-05-13 they **raised weekly limits ~50%**. Net effect:
**primary now rarely caps** — a genuinely hard week (15k+ turns, 4.7B raw
tokens) projects to ~19% of the weekly limit, not 100%. See
`memory/launchd-snapshot-path-fragility.md` and the deep-search trail in
this session's history.

Implications for code / doc / widget edits:

- **The binding constraint is now dollars, not weekly quota.** Usage
  credits are ON ($200/mo cap); overage is real money. The widget's Row 1
  identity card leads with the `extra` $ gate for this reason. Weekly
  quota pacing is now a near-dormant secondary.
- **Overflow is a Pro warm spare** kept to preserve the OAuth token,
  account state, and `claude2` shim — NOT a daily driver. Pro limits are
  ~1/20th, so even light spare use maxes its 5h session (a 99% overflow
  session is *expected*, not a bug). If primary ever actually caps, the
  play is Settings → Billing → Adjust plan → Max on claude2, not "ride
  out the week on Pro."
- **Bridge mode + overflow-promotion are now almost always dormant** (see
  below). Do NOT delete them — they're correctness-critical in the rare
  cap event — but don't expect them to fire in normal operation.
- Capped-mode tooltips referencing "Both accounts Max 20x" / "$10k
  API-equivalent" are stale — overflow is Pro now.
- `OVERFLOW_DOWNGRADE_SCHEDULED` in `ubersicht/cc-usage.jsx` stays `true`.
  If claude2 is ever bumped back to Max, flip that constant AND the
  `ACCOUNTS` overflow entry in `claude_code_usage.py` back together.

## Bridge mode (overflow weekly re-anchor)

When primary is capped (≥95%) AND primary's reset is sooner than the
overflow account's own 7-day reset, the `--widget-json` path attaches a
`bridge` sub-object to `overflow.weekly` with re-anchored pacing:
`reset_label` / `days_left` / `ideal_pct` / `projected_pct` /
`safe_pct_per_day` computed against **primary's reset**, not overflow's
own 168h cycle. The JSX WEEK card reads from `weekly.bridge.*` when
`applied=true` and falls back to `weekly.*` otherwise, with the real 7d
`projected_pct` shown inline for comparison. Do not "clean up" the
bridge branch when testing in non-capped states — it's dormant by
design and correctness-critical during the 1–4 day bridge window after
a cap.

The `--snapshot-only` launchd path ALSO must survive API failures
without killing the backfill half. The snapshot insert and the
incremental backfill are independent: an API 429 storm (hours long,
Retry-After: 0, no useful retry hint) must not freeze the turns
table, because the turns table is what keeps the extrapolation alive.

## Active windows banner (context fill of 1M)

The widget's topmost row is a horizontal strip of every currently-active
Claude Code window with a mini fill bar against the 1M context ceiling
(the `context-1m-2025-08-07` beta). Purpose: give the user a single
always-visible "which open window is about to compact" readout so they
can `/handoff` on their own terms instead of letting auto-compact fire.

Thresholds (1M-anchored, NOT the 280k $/reply bands used by the row-2
LIVE card — two different questions). Tuned to cost-per-turn, not
auto-compact: at >150k context you're already paying ~5× per turn vs
fresh, so the bands are aggressive on purpose:
  <40% fill   → neutral cyan
  ≥40% fill   → amber (start thinking — cost-per-turn climbing)
  ≥65% fill   → underlined white + "⚠ HANDOFF" flag (last comfortable
                handoff window before turns get expensive AND slow)

Data source is `live_session_stats()` in `claude_code_usage.py`, which
MUST scan BOTH project roots — `~/.claude/projects/` (primary account)
AND `~/.claude-alt/projects/` (overflow account) — because each open
Claude Code window writes only to the root matching its active account.
A single-root scan misses half the live windows when both accounts are
in use. Do not "simplify" this back to a single root.

Sessions are keyed by `(root_name, project_dir)` so the same project
open under both accounts surfaces as two distinct windows.
