# Multi-Account Strategy — Research & Implementation Plan

**Date:** 2026-04-12 (overflow upgraded Pro → Max 20x on 2026-04-15)
**Context:** Andy consistently exceeds Max 20x weekly allotment (~171% one week, 54% midweek another). Extra usage overage is 50x worse value than subscription tokens. A second account as overflow is dramatically more cost-efficient.

> **2026-04-15 update:** the overflow account was upgraded from Pro
> ($20/mo) to Max 20x ($200/mo) after burning through Pro's allotment
> mid-week and being forced into either-pay-overage-or-stop. Total
> subscription cost is now $400/mo for two symmetric Max 20x accounts.
> The "Pro relief valve" framing below is historical — both accounts
> now carry full Max 20x allotments.

---

## What we confirmed empirically

### 1. `CLAUDE_CONFIG_DIR` isolates everything
Setting `CLAUDE_CONFIG_DIR=~/.claude-alt` creates a fully independent Claude Code installation:
- Own projects dir: `~/.claude-alt/projects/*/*.jsonl`
- Own sessions, settings, memory — all scoped to the alt dir
- Running sessions on `~/.claude` are **completely unaffected** by alt-dir activity

### 2. Keychain entries are separate
Each config dir gets its own macOS keychain entry:
- Default (`~/.claude`): `Claude Code-credentials` (no suffix, legacy format)
- Alt (`~/.claude-alt`): `Claude Code-credentials-bae1e975` (SHA256 prefix of dir path)

Computed via: `echo -n "$HOME/.claude-alt" | shasum -a 256 | cut -c1-8` → `bae1e975`

### 3. JSONL files land in the alt config dir
Test message from `tilloat@gmail.com` produced:
```
~/.claude-alt/projects/-Users-at/16470cf2-9f32-4775-94bf-a0bfe672fac4.jsonl
~/.claude-alt/history.jsonl
```
**Not** in `~/.claude/projects/`. Complete separation.

### 4. Free accounts cannot use Claude Code
OAuth flow blocks with "Claude Max or Pro is required to connect to Claude Code." Minimum is Pro ($20/mo).

### 5. Extra usage is a toggle
Can be disabled/re-enabled at any time in Settings > Usage. Disabling does not affect the Max subscription. It's not automatic — you get a notification when hitting the limit and choose to continue.

---

## Accounts

| Account | Email | Plan | Monthly cost | Role |
|---|---|---|---|---|
| Primary | andytillo (main) | Max 20x | $200/mo | Daily driver, all projects |
| Overflow | tilloat@gmail.com | Max 20x | $200/mo | Full mirror — kicks in when primary hits weekly cap |

### Access

```bash
# Primary (default, no env var needed)
claude

# Overflow
CLAUDE_CONFIG_DIR=~/.claude-alt claude
# or with alias:
claude2
```

---

## Cost-optimized usage order

1. **Max 20x included allotment** — ~$5,000+ API-equivalent value for $200/mo
2. **Pro overflow account** — ~$500+ API-equivalent value for $20/mo
3. **Extra usage overage** (currently enabled, should disable) — $1 = $1 of tokens at API rates

**Action: Turn off extra usage on the Max 20x account** until both subscription allotments are exhausted. Only re-enable as a last resort. Current month has already burned $124.75 in overage that could have been absorbed by the Pro account.

**Projected savings:** ~$170/mo ($400 → ~$230 for equivalent compute)

---

## The math (from real data, week of 2026-04-06)

Token burn at 54% weekly utilization:

| Category | Tokens | API rate | API cost |
|---|---|---|---|
| Input (uncached) | 80K | $5/MTok | $0.40 |
| Output | 20.1M | $25/MTok | $501.79 |
| Cache creation | 80.0M | $6.25/MTok | $499.79 |
| Cache read | 3,772.9M | $0.50/MTok | $1,886.44 |
| **Total** | | | **~$2,888** |

Full 100% weekly allotment ≈ **~$5,350** in API-equivalent value.
$1 in subscription buys ~$50 of compute. $1 in overage buys $1.

---

## cc-usage changes needed for multi-account support

### Backfill (`claude_usage_backfill.py`)
- Add `~/.claude-alt/projects/*/*.jsonl` as second glob
- Tag rows with account identifier (email or config dir)

### OAuth snapshots (`claude_code_usage.py`)
- Read both keychain entries:
  - `Claude Code-credentials` (primary)
  - `Claude Code-credentials-bae1e975` (overflow)
- Poll `/api/oauth/usage` for each, store separate snapshot rows
- Add `account` column to `snapshots` table

### Widget (`ubersicht/cc-usage.jsx`)
- Display both accounts' session % and weekly %
- Or: combined view showing total remaining capacity across both

### Extrapolation (`_extrapolate_live`)
- Per-account `%-per-MTok` ratios (different plan tiers)
- Or: only extrapolate for whichever account is currently active

### CLI display
- Show both accounts in the panel
- Pacing advice should factor in total remaining capacity across both

---

## Shell setup (not yet wired)

```bash
# ~/.zshrc — add after existing cc-usage alias
alias claude2='CLAUDE_CONFIG_DIR=~/.claude-alt claude'
```

---

## Open questions

1. Should `/handoff` files from account 1 be readable by account 2? (Yes — handoffs live in `~/.claude/handoffs/`, need to check if account 2 can read them or if we need a shared location)
2. Should CLAUDE.md / skills / settings be shared or independent? (The madewithlove blog recommends NOT syncing auth/caches but YES syncing skills/agents)
3. Widget: combined single bar or two separate bars?
4. Should the launchd snapshot agent poll both accounts?

---

## Sources

- [Multiple accounts gist (KMJ-007)](https://gist.github.com/KMJ-007/0979814968722051620461ab2aa01bf2) — keychain hash format
- [Medium: Setting up multiple accounts](https://medium.com/@buwanekasumanasekara/setting-up-multiple-claude-code-accounts-on-your-local-machine-f8769a36d1b1)
- [madewithlove: Running multiple accounts](https://madewithlove.com/blog/running-multiple-claude-accounts-without-logging-out/)
- [Claude Help: Extra usage](https://support.claude.com/en/articles/12429409-manage-extra-usage-for-paid-claude-plans)
- [Claude Help: Max plan](https://support.claude.com/en/articles/11049741-what-is-the-max-plan)
- [Reddit: Cache fix (Rangizingo)](https://reddit.com/r/ClaudeAI/comments/1s8zxt4/) — 2.7k upvotes
- [Reddit: Solo dev 2x accounts](https://reddit.com/r/ClaudeAI/comments/1pjk1mg/)
- [Reddit: Subscriptions 36x cheaper than API](https://reddit.com/r/ClaudeAI/comments/1qpcj8q/)
- [Reddit: Never rate limited analysis](https://reddit.com/r/ClaudeAI/comments/1s5r0hj/)
- [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing) — Opus 4.6: $5/$25 per MTok
