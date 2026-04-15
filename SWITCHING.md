# Two-Account Switching Guide

You have two Claude Code accounts. The widget manages the whole lifecycle
automatically — this doc is the reference for your first time through.

## Accounts

| Account | Command | Plan | Role |
|---------|---------|------|------|
| Primary | `claude` | Max 20x ($200/mo) | Daily driver, Mon-Tue |
| Overflow | `claude2` | Max 20x ($200/mo) | Relief valve, Tue-Fri |

## What happens each week

### Monday-Tuesday: normal mode

You use `claude` as usual. The widget Row 3 shows:

```
pro · overflow   switch ~tue 6:58am (43h) · sess 0% · wk 1%
```

That "tue 6:58am" is a live countdown — the exact minute the primary
account will hit 100% at your current pace. It recalculates every 60
seconds. If you slow down, the time pushes later. If you speed up, it
pulls earlier.

### Tuesday (or whenever primary hits ~95%): SWITCH

The widget changes:

1. Row 3 flashes: **`▶ SWITCH NOW  claude2`**
2. Rows 1+2 **flip** to show the overflow account's data — full
   sparklines, pacing, today stats. The header shows "claude code · max 20x".
3. Row 3 becomes: `max 20x · capped  resets fri 6:00am → switch back`

**What you do:**

1. Open a new terminal tab
2. Type `claude2`
3. That's it. Work normally. Your existing primary sessions won't
   respond — just close them.

`claude2` is an alias for `CLAUDE_CONFIG_DIR=~/.claude-alt claude`.
It uses a completely separate login, keychain entry, and JSONL history.
Your projects, CLAUDE.md files, and git repos are shared — only the
account and quota are different.

### Tuesday-Friday: running on overflow

The overflow account is now your daily driver. The widget shows its
full instrument panel (session%, weekly%, MTWTFSS sparkline, pacing).

Row 3 shows the capped primary account with a countdown to its reset:

```
max 20x · capped   resets fri 6:00am (2.4d) → switch back to claude
```

### Friday 6am: SWITCH BACK

The primary account's weekly quota resets to 0%. The widget signals:

```
max 20x · capped   ▶ SWITCH BACK  claude
```

**What you do:**

1. Open a new terminal tab
2. Type `claude` (the normal command — no "2")
3. You're back on Max 20x for the new week

## If the overflow account also caps out (fumes mode)

Both accounts are Max 20x ($200/mo) with identical allotments. If you
burn through both in the same week, the widget escalates through two
stages:

### Stage 1: Running low (overflow weekly ≥80%)

Row 3 changes to amber and shows the overflow burn rate:

```
max 20x · capped   resets fri 6:00am (2.4d) · overflow 83% running low
```

This is your heads-up — you have a day or less of overflow left.

### Stage 2: BOTH CAPPED (overflow weekly ≥95%)

Row 3 flashes:

```
▶ BOTH CAPPED — WAIT OR PAY
```

Hover for the tooltip with your two options:

- **Option A:** Wait for whichever account resets first (usually
  primary — Friday 6am). Switch back with `claude` once it does.
- **Option B:** Re-enable extra usage on whichever account resets
  sooner (claude.ai → Settings → Usage → toggle on). This charges at
  API rates ($1=$1, ~50x worse than subscription tokens) — last resort
  only. By the time both Max 20x accounts are capped you've already
  consumed roughly $10k of API-equivalent value that week.

## Quick reference

| Situation | Widget shows | You type |
|-----------|-------------|----------|
| Normal (Mon-Tue) | `switch ~tue 6:58am` | `claude` |
| Primary capped | `▶ SWITCH NOW claude2` | `claude2` |
| Running on overflow | `resets fri 6:00am` | `claude2` |
| Overflow running low | `overflow 83% running low` | `claude2` (keep going) |
| Both near cap | `▶ BOTH CAPPED — WAIT OR PAY` | Hover for options |
| Primary resets | `▶ SWITCH BACK claude` | `claude` |

## How tracking works

Both accounts are tracked in the same SQLite database. The 15-minute
launchd agent polls both accounts' usage APIs. The backfill scans both
`~/.claude/` and `~/.claude-alt/` JSONL files. Everything is tagged
with an `account` column so the per-account stats never mix.

The widget's switch ETA is computed from: `(100% - current%) / burn_rate`,
where burn_rate is the average %/hour across the current weekly window.
It updates every 60 seconds on the widget refresh cycle.
