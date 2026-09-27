# Codex in cc-usage

The Codex row adds account quota windows, reset countdowns, a 99%-by-reset
budget, recent quota pacing, today's tokens/responses, and seven-day daily,
project, and model breakdowns. Subscription cost is configured as $100/month
from Andy's plan; it is not inferred from tokens or treated as API credit.

## Data and refresh

- `codex_usage.py --collect` imports local `CODEX_HOME/sessions` and
  `archived_sessions` JSONL files incrementally into `codex_*` tables in the
  existing SQLite DB. The default home is `~/.codex`.
- Live quota uses the installed Codex binary's documented app-server
  `account/rateLimits/read` method, at most once every 15 minutes. It uses the
  existing signed-in account and does not start a model turn or parse auth files.
- The collector runs every minute. It atomically writes
  `data/codex_usage.json`. The existing widget reads only that cache, so
  network failures cannot block Claude's render path.
- A quota observation in a transcript can update the cache between live polls.
  Quota older than 30 minutes is marked stale. An elapsed reset is marked
  "awaiting reset reading", never fabricated as 0%. A collector that has not
  refreshed in three minutes is marked stale separately.
- Only windows the service actually returns are shown, with their actual
  durations. A weekly window in the `primary` slot is not mislabeled as 5h.
- The stats cover seven local calendar days (`CC_USAGE_TZ`, default Pacific),
  not necessarily the same date range as the quota window.

## Counting correctly

Modern logs contain `token_usage_record` entries: one response's `usage`,
keyed globally by `response_id`, is counted once. Replayed/forked transcripts
cannot count the same response twice. Cached input is part of input, and
reasoning is part of output; total tokens are input + output.

For older sessions without these records, cumulative `token_count` deltas
are used. Repeated snapshots contribute nothing; a decreasing counter
establishes a new baseline. Response-level records take precedence for a
session. Mixed-format sessions that gain response records partway through
may undercount earlier legacy-only activity; they never sum both sources.

Offsets, parser state, and inserts are committed together per file. Partial
last lines are retried on the next run. Only usage/session/model metadata is
stored, not prompts, tool output, or auth credentials.

Local totals exclude cloud/remote activity without local transcripts. Account
quota can include that activity. Missing days mean no recorded local usage,
not proof of no account usage. Pacing uses quota changes within the same reset
window over up to 24h, with at least 15 minutes between observations. Short
bursts can make projections noisy; no fixed token-to-quota conversion is used.

This first version assumes one signed-in Codex account per collected home.
Account switching/multiple Codex accounts, active-session UI, and Codex handoff
controls are not implemented. This is read-only monitoring of Codex.

## Install / verify

First collect and validate:

```sh
python3 codex_usage.py --collect --codex-bin /absolute/path/to/codex
python3 tests/test_codex_usage.py
node scripts/jsxcheck.js ubersicht/cc-usage.codex.jsx
node scripts/jsxcheck.js ubersicht/cc-usage.jsx
```

Install the minute-by-minute collector using the same Full Disk Access Python
as the existing widget:

```sh
python3 scripts/install_codex.py --python /absolute/path/to/FDA/python3 \
  --codex-bin /absolute/path/to/codex
```

`--prepare-only` renders the launchd plist into `data/` without installing it.
The installed agent is `com.cc-usage.codex`; logs are `data/codex_usage.log`.
The installer refreshes the existing widget symlink, or updates the main JSX
and changed display modules in an existing copy installation. Existing widget config
and Claude agents are preserved. To stop automatic collection without deleting
anything: `launchctl bootout gui/$(id -u)/com.cc-usage.codex`.

To inspect cached data: `python3 codex_usage.py`. To import local logs without
any live quota request: `python3 codex_usage.py --collect --offline`.

App-server reference: https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt

## Compact layout

The normal desktop layout uses four bands: windows + spare/Mac status,
Claude quota, activity + contributors, and Codex. Cards wrap on narrower
screens; detailed breakdowns stay on hover. Handoff controls and capped-account
alerts remain available.
