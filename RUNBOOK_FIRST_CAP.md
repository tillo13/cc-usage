# First-cap runbook — saved Mon Apr 13 evening

> **HISTORICAL — completed 2026-04-15.** This runbook covered the
> first-ever Max 20x cap and the Pro → Max 5x upgrade plan for the
> overflow account. In practice the overflow was upgraded straight to
> Max 20x ($200/mo) on Apr 15, skipping the Max 5x intermediate step.
> Both accounts are now Max 20x; see `MULTI_ACCOUNT_PLAN.md` for the
> current state. Kept here as a record of the first-cap experience.

Context for morning-you: this is the first time hitting the Max 20x
weekly cap on this new heavier work schedule. Primary was at ~90% at
6pm Mon, expected to land ~93% by bedtime after a 1h wrap-up.

## Current state (as of Mon Apr 13 ~6pm)

- **Primary (Max 20x)**: ~90% weekly, resets Fri 6am (≈2.5 days out)
- **Overflow (Pro, $20/mo)**: ~2% weekly, fresh
- **Plan for the week**: bridge on Pro tonight → upgrade Pro → Max 5x ($100) when it caps → ride out until Fri primary reset

At your current burn rate (~14.5h/day, ~6.4k turns/day), Pro lasts
roughly **4–5 hours** before capping. That's the trigger for the
upgrade step.

## Runbook

### 1. When primary hits 95% (widget swaps to claude2-active)
- Finish in-flight task. Don't start a new one on primary.
- `Cmd-W` every open Claude Code window.
- Fresh terminal tabs → `claude2` in each → resume work.

### 2. When claude2 caps (~5h later, widget shows `▶ UPGRADE OVERFLOW`)
- Browser → claude.ai → log in as overflow account.
- Settings → Plan → **Upgrade to Max 5x ($100/mo)**.
- Return to terminal. Existing `claude2` windows keep working on next
  request — quota just grew under you. No re-auth, no restart.

### 3. When primary resets (Fri 6am, widget shows `▶ SWITCH BACK`)
- Close `claude2` windows, reopen with plain `claude`.
- Back to normal rotation.

## Cosmetic cleanup (optional, post-upgrade)

After the Max 5x upgrade, update the widget label so the header stops
saying "Pro":

```python
# claude_code_usage.py:73
"overflow": {"keychain": "Claude Code-credentials-bae1e975",
             "label": "Max 5x",   # was "Pro"
             "tier": "max_5x"},   # was "pro"
```

Then re-copy the widget to the installed location:
`cp ubersicht/cc-usage.jsx "$HOME/Library/Application Support/Übersicht/widgets/cc-usage.jsx"`
(CSS/JSX copy is only needed if you also edit the JSX; Python-side
changes are picked up by the next 15-min snapshot automatically.)

## "Wire it into the widget" todo (morning task)

In this conversation you said yes-ish to wiring this exact runbook
into the fumes-mode tooltip so future-you doesn't need this file. The
tooltip already lists the 3 options at `ubersicht/cc-usage.jsx:1056`
(the `FUMES MODE` branch) — just need to thread in the 4-step
close-windows → claude2 → upgrade → back-to-claude sequence.

## Reddit context (from tonight's research)

You're not alone on this path. `ming86` and others run multiple Max
accounts in rotation (github.com/ming86/cc-account-switcher,
hunhee98/claude-account, realiti4/claude-swap). You're in a small
cohort, not a tier of one. The multi-account + upgrade-overflow flow
you just set up is the well-worn path for devs running 14+ hours/day.

## Morning prompt to Claude

Something like:
> "Read RUNBOOK_FIRST_CAP.md and help me execute — I'm picking up
> where I left off last night."
