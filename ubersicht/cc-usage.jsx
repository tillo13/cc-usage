// cc-usage — Claude Code quota desktop banner for Übersicht
//
// ══════════════════════════════════════════════════════════════════════
//   DESIGN: "PRECISION INSTRUMENT"
// ══════════════════════════════════════════════════════════════════════
//
// Think Bloomberg Terminal meets Swiss railway clock meets Braun calculator.
// A measurement device, not a dashboard. Every element serves calibration.
//
// Principles:
//   · Editorial typographic hierarchy — tiny uppercase micro-labels sit
//     above bigger tabular-monospace values, like a newspaper caption
//     over a headline.
//   · Hairline rules (1px) separate sections like newspaper columns.
//   · Sharp geometry — zero rounded corners on bars, ticks, dividers.
//     Instruments are not friendly, they are precise.
//   · Monochromatic base (pure black + pure white + steel greys) with
//     a single electric cyan accent. Amber only as a warning semaphore.
//   · Progress bars have quarter-tick calibration marks and a target
//     marker (white vertical hairline) at the "ideal" position for the
//     weekly bar — so you literally see "where I should be" vs
//     "where I am" on the instrument.
//   · A pulsing status dot near the updated-time, the only moving
//     element, signals the widget is live.
//
// Colorblind-safe palette:
//   #000000 ink bed
//   #FFFFFF pure white (primary numerics)
//   #4AE3FF electric cyan (accent, "on pace", label color)
//   #FFB800 saturated amber (warning — never red)
//   #B8C8E0 ice (hint text)
//   #5A6B82 steel (muted dividers and units)
//
// The "critical" state doesn't add another hue — it underlines the
// number and sets it pure white bold, so colorblind readers still
// distinguish it from amber/cyan via shape, not color.
//
// ══════════════════════════════════════════════════════════════════════
//
// Data source: claude_code_usage.py --widget-json
//
// This file should be COPIED (not symlinked — FSEvents ignores symlink
// targets) into ~/Library/Application Support/Übersicht/widgets/ after
// every edit. See the README for one-line install.
//
// ══════════════════════════════════════════════════════════════════════
//   USER CONFIG — edit these two paths after copying the widget
// ══════════════════════════════════════════════════════════════════════
//
// PYTHON_BIN must point at a Python 3 interpreter that:
//   (a) has the `requests` package installed, AND
//   (b) has macOS "Full Disk Access" / Desktop TCC permission granted
//       (System Settings → Privacy & Security → Full Disk Access).
//   The stock /usr/local/bin/python3 usually FAILS on (b) — the launchd
//   agent and Übersicht both run under sandboxed contexts that can't
//   read ~/.claude/projects without an explicitly permitted interpreter.
//   The simplest fix is to use a virtualenv whose parent directory has
//   already been granted Full Disk Access (most devs already have one).
//
// REPO_ROOT is the absolute path to this cloned cc_usage repo. The
// widget invokes `${REPO_ROOT}/claude_code_usage.py --widget-json`.
//
const PYTHON_BIN = "/Users/at/Desktop/code/kicksaw/venv_kicksaw/bin/python3"
const REPO_ROOT  = "/Users/at/Desktop/code/_infrastructure/cc_usage"

export const command =
  "PATH=/usr/bin:/bin:/usr/sbin:/sbin " +
  `${PYTHON_BIN} ${REPO_ROOT}/claude_code_usage.py --widget-json`

export const refreshFrequency = 60000

export const className = `
  top: 0;
  left: 0;
  right: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
  font-size: 11px;
  font-weight: 500;
  color: #FFFFFF;
  background:
    linear-gradient(180deg, rgba(6, 10, 18, 0.94) 0%, rgba(0, 0, 0, 0.94) 100%);
  backdrop-filter: blur(28px) saturate(180%);
  -webkit-backdrop-filter: blur(28px) saturate(180%);
  pointer-events: none;
  box-shadow:
    inset 0 1px 0 rgba(74, 227, 255, 0.14),
    inset 0 -1px 0 rgba(74, 227, 255, 0.55);
  -webkit-font-smoothing: antialiased;
  letter-spacing: 0;
  user-select: none;
  -webkit-user-select: none;

  .bar {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }

  .row {
    display: flex;
    align-items: center;
    padding: 0 22px;
    height: 26px;
  }
  .row2 {
    border-top: 1px solid rgba(74, 227, 255, 0.08);
    height: 22px;
    padding-top: 1px;
  }

  /* Hairline vertical rule separating cards — the newspaper column look. */
  .rule {
    width: 1px;
    height: 22px;
    background: linear-gradient(
      to bottom,
      rgba(184, 200, 224, 0) 0%,
      rgba(184, 200, 224, 0.22) 15%,
      rgba(184, 200, 224, 0.22) 85%,
      rgba(184, 200, 224, 0) 100%
    );
    margin: 0 16px;
    flex-shrink: 0;
  }
  .row2 .rule { height: 14px; margin: 0 14px; }

  /* CARD — row-1 variant stacks label over value. */
  .card {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    position: relative;
    pointer-events: auto;
    cursor: help;
    padding: 0 3px;
    flex-shrink: 0;
  }
  .card:hover { background: rgba(74, 227, 255, 0.06); }

  /* Row-2 cards are inline (label + value same line) for density. */
  .cardInline {
    flex-direction: row;
    align-items: center;
    gap: 10px;
  }

  /* Micro-label — the editorial caption. */
  .lbl {
    font-size: 8.5px;
    font-weight: 800;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #4AE3FF;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .lblDim { color: #5A6B82; }

  /* Value line — tabular monospace, the headline. */
  .val {
    font-family: "SF Mono", ui-monospace, "JetBrains Mono", "Menlo", monospace;
    font-size: 11.5px;
    font-weight: 500;
    color: #FFFFFF;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.005em;
    line-height: 1;
    display: flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
  }
  .row2 .val { font-size: 10.5px; }

  .num { font-weight: 700; color: #FFFFFF; }
  .dot {
    color: rgba(184, 200, 224, 0.30);
    font-weight: 400;
    padding: 0 1px;
    font-size: 10px;
  }
  .unit {
    color: #5A6B82;
    font-weight: 600;
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .hint {
    color: #B8C8E0;
    font-weight: 500;
  }

  /* ═══ Progress bar — the calibrated instrument ═══
     Track has quarter-tick calibration marks baked into the background.
     Two stacked fills: dim cyan = time elapsed, bright semantic = quota
     burned. A sharp white marker shows the "ideal" position (weekly only). */
  .pbar {
    display: inline-block;
    position: relative;
    width: 76px;
    height: 7px;
    background-color: rgba(184, 200, 224, 0.07);
    background-image: linear-gradient(
      to right,
      transparent 0,
      transparent calc(25% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(25% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(25% + 0.5px),
      transparent calc(25% + 0.5px),
      transparent calc(50% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(50% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(50% + 0.5px),
      transparent calc(50% + 0.5px),
      transparent calc(75% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(75% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(75% + 0.5px),
      transparent calc(75% + 0.5px),
      transparent 100%
    );
    border-top: 1px solid rgba(184, 200, 224, 0.28);
    border-bottom: 1px solid rgba(184, 200, 224, 0.28);
    flex-shrink: 0;
    vertical-align: middle;
    overflow: visible;
  }
  .fillTime {
    position: absolute;
    top: 0; left: 0; bottom: 0;
    background: rgba(74, 227, 255, 0.24);
  }
  .fillQuota {
    position: absolute;
    top: 0; left: 0; bottom: 0;
  }
  .idealMark {
    position: absolute;
    top: -2px;
    bottom: -2px;
    width: 1px;
    background: #FFFFFF;
    box-shadow: 0 0 4px rgba(255, 255, 255, 0.9);
    z-index: 2;
  }

  /* Semantic foreground colors — colorblind-safe.
     Crit is underlined so it is distinguishable by SHAPE, not just hue. */
  .good { color: #4AE3FF; font-weight: 700; }
  .warn { color: #FFB800; font-weight: 800; }
  .crit {
    color: #FFFFFF;
    font-weight: 900;
    text-decoration: underline;
    text-underline-offset: 2px;
    text-decoration-thickness: 1.5px;
  }
  .bgGood { background: #4AE3FF; }
  .bgWarn { background: #FFB800; }
  .bgCrit { background: #FFFFFF; }

  /* Live-session inline wrapper — one per active session in the LIVE card. */
  .liveSess {
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  /* Pace pill — tiny text chip after each bar */
  .pill {
    font-size: 8.5px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 1px 5px 0 5px;
    border: 1px solid currentColor;
    line-height: 1;
  }

  /* ═══ Day strip — minimal sparkline ═══
     Each day is a narrow column. Active hours set bar height. Today is
     marked with a 1px white cap outline. Future days show only a baseline
     tick so the eye reads "week ahead — unknown". */
  .spark {
    display: inline-flex;
    align-items: flex-end;
    gap: 3px;
    height: 14px;
    flex-shrink: 0;
  }
  .sparkCell {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    width: 9px;
    height: 14px;
    position: relative;
  }
  .sparkBar {
    width: 8px;
    background: rgba(74, 227, 255, 0.55);
  }
  .sparkBarToday {
    background: #4AE3FF;
    box-shadow: 0 0 0 1px #FFFFFF, 0 0 6px rgba(74, 227, 255, 0.8);
  }
  .sparkFuture {
    width: 8px;
    height: 1px;
    background: rgba(184, 200, 224, 0.20);
  }
  .sparkEmpty {
    width: 8px;
    height: 1px;
    background: rgba(184, 200, 224, 0.35);
  }
  .sparkLabel {
    position: absolute;
    top: -9px;
    font-size: 7.5px;
    font-weight: 800;
    color: #5A6B82;
    letter-spacing: 0.05em;
    line-height: 1;
  }
  .sparkLabelToday { color: #4AE3FF; }

  /* ═══ Updated time with live pulse ═══ */
  .updated {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 7px;
    font-family: "SF Mono", ui-monospace, "JetBrains Mono", monospace;
    font-size: 10px;
    font-weight: 600;
    color: #B8C8E0;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    flex-shrink: 0;
  }
  .pulse {
    display: inline-block;
    width: 6px;
    height: 6px;
    background: #4AE3FF;
    box-shadow: 0 0 6px #4AE3FF, 0 0 12px rgba(74, 227, 255, 0.6);
    animation: cc-pulse 2.4s ease-in-out infinite;
  }
  @keyframes cc-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.35; transform: scale(0.72); }
  }

  /* ═══ claude2 migration nudge ═══
     Soft (primary 85–94%): non-animated amber hint.
     Urgent (primary ≥97%): slow opacity blink demanding action. */
  .nudge {
    color: #FFB84D;
    font-family: "SF Mono", ui-monospace, "JetBrains Mono", monospace;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  .nudgeUrgent {
    color: #FF6B6B;
    font-family: "SF Mono", ui-monospace, "JetBrains Mono", monospace;
    font-weight: 800;
    letter-spacing: 0.02em;
    animation: cc-nudge 1.4s ease-in-out infinite;
  }
  @keyframes cc-nudge {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.35; }
  }

  /* ═══ Custom tooltip ═══
     Native title="" doesn't reliably render in Übersicht's WKWebView, so
     tooltips are absolute :hover divs. Matches the instrument aesthetic:
     sharp edges, hairline cyan border, monospace body, swiss header. */
  .tip {
    display: none;
    position: absolute;
    top: calc(100% + 10px);
    left: -6px;
    min-width: 340px;
    max-width: 500px;
    padding: 14px 18px 15px 18px;
    background: #000000;
    border: 1px solid #4AE3FF;
    box-shadow:
      0 20px 48px rgba(0, 0, 0, 0.85),
      0 0 0 1px rgba(74, 227, 255, 0.18),
      inset 0 0 32px rgba(74, 227, 255, 0.04);
    font-family: "SF Mono", ui-monospace, "JetBrains Mono", monospace;
    font-size: 11px;
    font-weight: 500;
    color: #B8C8E0;
    line-height: 1.55;
    white-space: pre-wrap;
    z-index: 99999;
    pointer-events: none;
    letter-spacing: 0;
  }
  .tipHead {
    display: block;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: #4AE3FF;
    margin-bottom: 9px;
    padding-bottom: 9px;
    border-bottom: 1px solid rgba(74, 227, 255, 0.30);
  }
  .tipKey { color: #5A6B82; font-weight: 600; }
  .tipVal { color: #FFFFFF; font-weight: 700; }
  .tipNote {
    display: block;
    margin-top: 9px;
    padding-top: 9px;
    border-top: 1px solid rgba(74, 227, 255, 0.18);
    color: #8A9BB8;
    font-style: italic;
  }
  .card:hover .tip { display: block; }
  .tipRight { left: auto; right: -6px; }

  .err { color: #FFB800; }
`

// ───────────────────────────────────────────────────────────────────
//   helpers
// ───────────────────────────────────────────────────────────────────

const fmtHM = (h) => {
  if (h == null || isNaN(h)) return "—"
  if (h < 0) h = 0
  const hours = Math.floor(h)
  const mins = Math.round((h - hours) * 60)
  if (hours === 0) return `${mins}m`
  return `${hours}h${String(mins).padStart(2, "0")}m`
}
const fmtHD = (h) => {
  if (h == null || isNaN(h)) return "—"
  if (h < 24) return fmtHM(h)
  const whole = Math.floor(h)
  const days = h / 24
  return `${whole}h/${days.toFixed(1)}d`
}
const paceClass = (d) => d == null ? "good" : d >= 40 ? "crit" : d >= 10 ? "warn" : "good"
const paceBgClass = (d) => d == null ? "bgGood" : d >= 40 ? "bgCrit" : d >= 10 ? "bgWarn" : "bgGood"
const paceWord = (d) => {
  if (d == null) return "ON PACE"
  if (d >= 40) return "CRITICAL"
  if (d >= 20) return "VERY HOT"
  if (d >= 10) return "HOT"
  if (d >= -10) return "ON PACE"
  return "COOL"
}
const clamp = (v) => Math.max(0, Math.min(100, v))

// ───────────────────────────────────────────────────────────────────
//   render
// ───────────────────────────────────────────────────────────────────

export const render = ({ output, error }) => {
  if (error) {
    return (
      <div className="bar">
        <div className="row"><span className="lbl err">CC-USAGE ERROR</span><span className="val err">{String(error).slice(0, 200)}</span></div>
      </div>
    )
  }
  if (!output) {
    return (
      <div className="bar">
        <div className="row"><span className="lbl">CLAUDE CODE</span><span className="val hint">loading…</span></div>
      </div>
    )
  }
  let d
  try { d = JSON.parse(output) }
  catch (e) {
    return (
      <div className="bar">
        <div className="row"><span className="lbl err">PARSE</span><span className="val err">{String(output).slice(0, 160)}</span></div>
      </div>
    )
  }
  // Multi-account support: new Python emits {accounts: {primary: {...}, overflow: {...}}}.
  // Backward compat: if d.session exists (old single-account format), treat d as primary.
  const primary = (d.accounts && d.accounts.primary) ? d.accounts.primary : (d.session ? d : null)
  const overflow = (d.accounts && d.accounts.overflow) ? d.accounts.overflow : null

  // Empty-payload sentinel: Python emits `{}` when it has neither a fresh
  // live fetch nor any DB snapshot to fall back on.
  if (!primary || !primary.session) {
    return (
      <div className="bar">
        <div className="row"><span className="lbl">CLAUDE CODE</span><span className="val hint">loading…</span></div>
      </div>
    )
  }

  // ── role swap: whichever account is ACTIVE gets the full Row 1+2 ──
  // When primary is capped (≥95%), the overflow becomes the daily driver
  // and gets promoted to the full instrument display. The capped primary
  // gets demoted to a compact "resets fri 6am → switch back" strip.
  const primaryCapped = (primary.weekly || {}).used_pct >= 95
  const hasOverflow = overflow && overflow.session
  const active = (primaryCapped && hasOverflow) ? overflow : primary
  const standby = (primaryCapped && hasOverflow) ? primary : overflow
  const activeLabel = active.account_label || "Max 20x"
  const standbyIsPrimary = primaryCapped && hasOverflow

  // ── claude2 migration nudge ──
  // Drives both the Row 1 pre-swap hint and the capped-strip urgent pulse.
  // Band on primary weekly %: 85–94% = soft hint (pre-swap, primary still active),
  // ≥97% = urgent pulse (post-swap, migration hasn't finished yet).
  const primaryWeekPctForNudge = clamp((primary.weekly || {}).used_pct || 0)
  const nudgeLevel = !hasOverflow ? null
    : primaryWeekPctForNudge >= 97 ? "urgent"
    : primaryWeekPctForNudge >= 85 ? "soft"
    : null

  const session = active.session || {}
  const weekly = active.weekly || {}
  const constraint = active.constraint || {}
  const today = active.today || {}
  const extra = active.extra
  const target = active.target_pct || 99

  // ── session math ──
  const sessTotal = 5.0
  const sessLeft = session.hours_left != null ? session.hours_left : 0
  const sessElapsed = Math.max(0, sessTotal - sessLeft)
  const sessTimePct = clamp((sessElapsed / sessTotal) * 100)
  const sessQuotaPct = clamp(session.used_pct || 0)
  const sessDelta = sessQuotaPct - sessTimePct
  const sessReset = session.reset_time_local || "—"
  const sessStart = session.started_at_local || "—"

  // ── weekly math ──
  // Bridge mode: when primary is capped and primary's reset comes before
  // overflow's own 7d reset, re-anchor the weekly card against primary's
  // reset (shorter horizon). The real 7d cycle is kept as a secondary hint.
  const bridge = (weekly.bridge && weekly.bridge.applied) ? weekly.bridge : null
  const weekLeft = bridge ? bridge.hours_left : (weekly.hours_left != null ? weekly.hours_left : 0)
  // Dim fill represents how far through the relevant horizon we are.
  // Bridge mode: horizon = (elapsed since overflow week started) + (hours to primary reset).
  const bridgeElapsed = bridge ? Math.max(0, 168.0 - (bridge.real_hours_left != null ? bridge.real_hours_left : 168.0)) : 0
  const bridgeTotal = bridge ? Math.max(0.01, bridgeElapsed + bridge.hours_left) : 168.0
  const weekElapsed = bridge ? bridgeElapsed : Math.max(0, 168.0 - weekLeft)
  const weekTimePct = bridge ? clamp((bridgeElapsed / bridgeTotal) * 100) : clamp((weekElapsed / 168.0) * 100)
  const weekQuotaPct = clamp(weekly.used_pct || 0)
  const weekDelta = weekQuotaPct - weekTimePct
  const weekReset = bridge
    ? (bridge.reset_time_local || bridge.reset_label || "—")
    : (weekly.reset_time_local || weekly.reset_label || "—")
  const vsIdeal = bridge ? bridge.vs_ideal_pct : weekly.vs_ideal_pct
  const idealPct = bridge ? bridge.ideal_pct : weekly.ideal_pct
  const projectedPct = bridge ? bridge.projected_pct : weekly.projected_pct
  const daysLeft = bridge ? bridge.days_left : weekly.days_left
  // Projection status: how far over/under target we'd land at current pace.
  // Treat anything >target+5 as an overshoot worth underlining; shade around target.
  const projDelta = projectedPct != null ? projectedPct - target : null
  const projClass = projDelta == null ? "good"
    : projDelta >= 40 ? "crit"
    : projDelta >= 10 ? "warn"
    : projDelta >= -10 ? "good"
    : "hint"

  const byDay = Array.isArray(weekly.by_day) ? weekly.by_day : []
  const maxDayH = Math.max(1, ...byDay.map((x) => x.active_hours || 0))

  const rate = constraint.rate_pct_per_active_hour
  // In bridge mode, recompute daily active-hour budget against the shorter
  // horizon (primary reset) — expands headroom correspondingly.
  const safeHours = (bridge && rate && rate > 0)
    ? (bridge.safe_pct_per_day / rate)
    : constraint.tomorrow_active_hours

  // ── live sessions (ALL currently-active Claude Code sessions) ──
  // Read directly from ~/.claude/projects/*.jsonl, sorted worst-first.
  // The Python side classifies each session into a band and attaches
  // `band` + `status_word` so the JSX just displays them.
  const liveSessions = Array.isArray(active.live_sessions) ? active.live_sessions : []
  const liveCount = liveSessions.length
  const liveTop = liveSessions.slice(0, 3)        // inline display
  const worst = liveSessions[0] || null            // drives the headline pill

  return (
    <div className="bar">

      {/* ════════════════════════════════════════════════════════════
           ROW 1 — PRIMARY CLOCKS
           [CC · TARGET]  │  [SESSION 5H]  │  [WEEK 168H]  │  [updated]
         ════════════════════════════════════════════════════════════ */}
      <div className="row">

        {/* IDENTITY */}
        <div className="card">
          <span className="lbl lblDim">claude code{standbyIsPrimary ? " · pro" : ""}</span>
          <span className="val">
            <span className="num">{target}</span>
            <span className="unit">%</span>
            <span className="hint">target</span>
          </span>
        </div>

        <span className="rule" />

        {/* SESSION — the rolling 5-hour window */}
        <div className="card">
          <span className="lbl">session <span className="lblDim">· 5h window</span></span>
          <span className="val">
            <span className="num">{fmtHM(sessElapsed)}</span>
            <span className="unit">in</span>
            <span className="dot">/</span>
            <span className="num">{fmtHM(sessLeft)}</span>
            <span className="unit">left</span>
            <span className="dot">·</span>
            <span className="hint">{sessReset}</span>
            <span className="dot"> </span>
            <span className="pbar">
              <span className="fillTime" style={{ width: sessTimePct + "%" }} />
              <span className={"fillQuota " + paceBgClass(sessDelta)} style={{ width: sessQuotaPct + "%" }} />
            </span>
            <span className={paceClass(sessDelta)}>{sessQuotaPct.toFixed(0)}%</span>
            <span className={"pill " + paceClass(sessDelta)}>{paceWord(sessDelta)}</span>
          </span>

          <div className="tip">
            <span className="tipHead">current 5-hour session</span>
            <span className="tipKey">started    </span><span className="tipVal">{sessStart}</span>{"\n"}
            <span className="tipKey">resets at  </span><span className="tipVal">{sessReset}</span>{"\n"}
            <span className="tipKey">time spent </span><span className="tipVal">{fmtHM(sessElapsed)}</span>{"  "}<span className="tipKey">({sessTimePct.toFixed(0)}% of window)</span>{"\n"}
            <span className="tipKey">time left  </span><span className="tipVal">{fmtHM(sessLeft)}</span>{"\n"}
            <span className="tipKey">quota used </span><span className="tipVal">{sessQuotaPct.toFixed(0)}%</span>
            {session.rate_pct_per_active_hour != null && [
              <span key="r1" className="tipKey">  @ </span>,
              <span key="r2" className="tipVal">{session.rate_pct_per_active_hour}%/active hr</span>,
            ]}
            {"\n\n"}
            <span className="tipKey">status     </span><span className={"tipVal " + paceClass(sessDelta)}>{paceWord(sessDelta)}</span>
            <span className="tipNote">
              The 5-hour session is a ROLLING window — it starts with your
              first message and ends exactly 5 hours later. Not a clock-
              time thing. When the bright fill is longer than the dim fill,
              you're burning quota faster than the clock.
            </span>
          </div>
        </div>

        <span className="rule" />

        {/* WEEK — the 168-hour window with ideal marker */}
        <div className="card">
          <span className="lbl">week <span className="lblDim">· 168h window</span></span>
          <span className="val">
            <span className="num">{fmtHD(weekElapsed)}</span>
            <span className="unit">in</span>
            <span className="dot">/</span>
            <span className="num">{fmtHD(weekLeft)}</span>
            <span className="unit">left</span>
            <span className="dot">·</span>
            <span className="hint">{weekReset}</span>
            <span className="dot"> </span>
            <span className="pbar">
              <span className="fillTime" style={{ width: weekTimePct + "%" }} />
              <span className={"fillQuota " + paceBgClass(weekDelta)} style={{ width: weekQuotaPct + "%" }} />
              {idealPct != null && (
                <span className="idealMark" style={{ left: idealPct + "%" }} />
              )}
            </span>
            <span className={paceClass(weekDelta)}>{weekQuotaPct.toFixed(0)}%</span>
            {vsIdeal != null && [
              <span key="vd" className="dot">·</span>,
              <span key="vv" className={paceClass(vsIdeal)}>
                {vsIdeal >= 0 ? "+" : ""}{vsIdeal.toFixed(2)}
              </span>,
              <span key="vu" className="unit">vs ideal</span>,
            ]}
            {projectedPct != null && [
              <span key="pd" className="dot">→</span>,
              <span key="pv" className={projClass}>
                {projectedPct.toFixed(0)}%
              </span>,
              <span key="pu" className="unit">proj</span>,
            ]}
            {bridge && [
              <span key="bd" className="dot">·</span>,
              <span key="bl" className="unit">7d</span>,
              bridge.real_projected_pct != null && (
                <span key="bp" className={
                  bridge.real_projected_pct >= target + 40 ? "crit"
                  : bridge.real_projected_pct >= target + 10 ? "warn"
                  : "hint"
                }>{bridge.real_projected_pct.toFixed(0)}%</span>
              ),
              <span key="bu" className="unit">proj</span>,
              <span key="bv" className="hint">(→{bridge.real_reset_time_local} · {bridge.real_days_left != null ? bridge.real_days_left.toFixed(1) + "d" : "—"})</span>,
            ]}
            {!standbyIsPrimary && nudgeLevel && [
              <span key="nd" className="dot">·</span>,
              <span key="nu" className="unit">new:</span>,
              <span key="nv" className={nudgeLevel === "urgent" ? "nudgeUrgent" : "nudge"}>
                claude2
              </span>,
            ]}
          </span>

          <div className="tip">
            <span className="tipHead">weekly quota {bridge ? "· bridge mode" : "· 168-hour window"}</span>
            {bridge && [
              <span key="bn1" className="tipNote">
                Primary account is capped — pacing this overflow account
                against primary's reset ({bridge.reset_time_local}), not its
                own 7-day reset. Once primary resets, switch back to
                `claude` and this account goes dormant until the next cap.
              </span>,
              "\n\n",
            ]}
            <span className="tipKey">resets at  </span><span className="tipVal">{weekReset}</span>{bridge ? <span className="tipKey">  (bridge horizon)</span> : null}{"\n"}
            {bridge && [
              <span key="br1" className="tipKey">7d reset   </span>,
              <span key="br2" className="tipVal">{bridge.real_reset_time_local}</span>,
              <span key="br3" className="tipKey">  ({bridge.real_days_left != null ? bridge.real_days_left.toFixed(1) : "—"}d · real cycle, safety net)</span>,
              "\n",
            ]}
            <span className="tipKey">time spent </span><span className="tipVal">{fmtHD(weekElapsed)}</span>{"  "}<span className="tipKey">({weekTimePct.toFixed(0)}% of week)</span>{"\n"}
            <span className="tipKey">time left  </span><span className="tipVal">{fmtHD(weekLeft)}</span>{"\n"}
            <span className="tipKey">quota used </span><span className="tipVal">{weekQuotaPct.toFixed(0)}%</span>{"\n"}
            {idealPct != null && [
              <span key="i1" className="tipKey">ideal now  </span>,
              <span key="i2" className="tipVal">{idealPct.toFixed(2)}%</span>,
              <span key="i3" className="tipKey">  (linear to {target}%)</span>,
              "\n",
            ]}
            {vsIdeal != null && [
              <span key="v1" className="tipKey">vs ideal   </span>,
              <span key="v2" className={"tipVal " + paceClass(vsIdeal)}>
                {vsIdeal >= 0 ? "+" : ""}{vsIdeal.toFixed(2)} points {vsIdeal >= 0 ? "HOT" : "cool"}
              </span>,
              "\n",
            ]}
            {projectedPct != null && [
              <span key="p1" className="tipKey">projected  </span>,
              <span key="p2" className={"tipVal " + projClass}>
                {projectedPct.toFixed(1)}% by reset
              </span>,
              <span key="p3" className="tipKey">  (if pace holds{bridge ? ", to primary reset" : ""})</span>,
              "\n",
            ]}
            {bridge && bridge.real_projected_pct != null && [
              <span key="rp1" className="tipKey">projected 7d </span>,
              <span key="rp2" className="tipVal">{bridge.real_projected_pct.toFixed(1)}%</span>,
              <span key="rp3" className="tipKey">  (same pace over full 7-day cycle)</span>,
              "\n",
            ]}
            {"\n"}
            <span className="tipKey">status     </span><span className={"tipVal " + paceClass(weekDelta)}>{paceWord(weekDelta)}</span>
            <span className="tipNote">
              The white hairline on the bar marks where you SHOULD be right
              now if you were pacing linearly toward {target}% by reset. If
              the bright fill is past the white marker, you're running hot.
            </span>
          </div>
        </div>

        <span className="updated">
          <span className="pulse" />
          <span>{d.updated_pt || primary.updated_pt || "—"}</span>
        </span>
      </div>

      {/* ════════════════════════════════════════════════════════════
           ROW 2 — SUPPORTING INSTRUMENTS
           [DAYS sparkline]  │  [SAFE PACE]  │  [TODAY]  │  [EXTRA $]
         ════════════════════════════════════════════════════════════ */}
      <div className="row row2">

        {/* DAYS — 8-column sparkline of active hours since weekly reset */}
        <div className="card cardInline">
          <span className="lbl">days</span>
          <span className="spark">
            {byDay.map((day) => {
              const h = day.active_hours || 0
              const pct = (h / maxDayH) * 100
              const barH = h > 0 ? Math.max(2, (pct / 100) * 12) : null
              return (
                <span key={day.date} className="sparkCell">
                  <span className={"sparkLabel " + (day.is_today ? "sparkLabelToday" : "")}>
                    {day.dow.slice(0, 1)}
                  </span>
                  {barH != null ? (
                    <span
                      className={"sparkBar " + (day.is_today ? "sparkBarToday" : "")}
                      style={{ height: barH + "px" }}
                    />
                  ) : day.is_future ? (
                    <span className="sparkFuture" />
                  ) : (
                    <span className="sparkEmpty" />
                  )}
                </span>
              )
            })}
          </span>

          <div className="tip">
            <span className="tipHead">days this week</span>
            {byDay.map((day, i) => {
              const mark = day.is_today ? "●" : (day.is_future ? "·" : " ")
              return (
                <span key={day.date}>
                  <span className={day.is_today ? "tipVal good" : "tipKey"}>
                    {mark} {day.dow}  {String(day.active_hours).padStart(2)}h  {String(day.turns.toLocaleString()).padStart(6)} turns  ~{day.pct_share.toFixed(0)}%
                  </span>
                  {"\n"}
                </span>
              )
            })}
            <span className="tipNote">
              Bar height = active hours worked that day. Today is outlined.
              Share ≈ percent of weekly quota consumed (approximated from
              per-day token counts — the API doesn't expose per-day % directly).
            </span>
          </div>
        </div>

        <span className="rule" />

        {/* LIVE SESSIONS — ALL currently-active Claude Code windows, ranked
            worst-first. Shows up to 3 inline so the nag covers every open
            session, not just whichever you last touched. Full list in tip.
            Bands from our own 7-day usage study: FRESH→NORMAL→HANDOFF→COMPACT. */}
        {liveCount > 0 && [
          <div key="lvc" className="card cardInline">
            <span className="lbl">
              live{liveCount > 1 ? <span className="lblDim"> ({liveCount})</span> : null}
            </span>
            <span className="val">
              {liveTop.map((s, i) => (
                <span key={s.session_id || i} className="liveSess">
                  {i > 0 && <span className="dot">·</span>}
                  <span className="hint">{s.project || "?"}</span>
                  <span className="dot"> </span>
                  <span className={"num " + s.band}>{s.turns}</span>
                  <span className="unit">/</span>
                  <span className={"num " + s.band}>
                    {s.context_k != null ? s.context_k.toFixed(0) : "—"}
                  </span>
                  <span className="unit">k</span>
                </span>
              ))}
              {worst && (
                <span className={"pill " + worst.band}>{worst.status_word}</span>
              )}
            </span>

            <div className="tip">
              <span className="tipHead">active claude code sessions · forward cost per reply</span>
              {liveSessions.map((s, i) => (
                <span key={s.session_id || i}>
                  <span className={"tipVal " + s.band}>
                    {(s.status_word || "").padEnd(8)}
                  </span>
                  <span className="tipKey">  </span>
                  <span className="tipVal">{(s.project || "?").padEnd(22)}</span>
                  <span className="tipKey">  ctx </span>
                  <span className={"tipVal " + s.band}>
                    {(s.context_k != null ? s.context_k.toFixed(0) : "—").padStart(4)}k
                  </span>
                  <span className="tipKey">  → </span>
                  <span className={"tipVal " + s.band}>
                    ${s.cost_per_reply_usd != null ? s.cost_per_reply_usd.toFixed(3) : "—"}/reply
                  </span>
                  <span className="tipKey">  turns {String(s.turns).padStart(4)}</span>
                  {"\n"}
                </span>
              ))}
              <span className="tipNote">
                Bands are driven by CONTEXT SIZE, not turn count. Context
                determines forward per-reply cache-read cost — turns are
                sunk. A 500-turn / 60k session is cheap to continue; a
                40-turn / 350k session is expensive.
                {"\n"}  FRESH    &lt;60k ctx    &lt;$0.03/reply
                {"\n"}  NORMAL   60–150k      $0.03–$0.075/reply
                {"\n"}  HANDOFF  150–280k     $0.075–$0.14/reply
                {"\n"}  COMPACT  280k+        &gt;$0.14/reply  ← act
                {"\n\n"}Costs assume Opus cache-read at $0.50/mtok. Each
                reply pays this FLOOR just to re-read history; thinking,
                new input, and tool output are extra on top.
                {"\n\n"}Run /handoff → fresh window → /resume to reset.
              </span>
            </div>
          </div>,
          <span key="lvr" className="rule" />,
        ]}

        {/* SAFE PACE — the forecast instrument */}
        <div className="card cardInline">
          <span className="lbl">safe pace</span>
          <span className="val">
            {safeHours != null ? [
              <span key="sh" className="num good">{safeHours.toFixed(1)}</span>,
              <span key="sg" className="unit">h/active day</span>,
              daysLeft != null && <span key="sd" className="dot">×</span>,
              daysLeft != null && <span key="sn" className="num">{daysLeft.toFixed(1)}</span>,
              daysLeft != null && <span key="su" className="unit">d</span>,
              <span key="sa" className="dot">→</span>,
              <span key="sp" className="hint">{target}% lands</span>,
            ] : (
              <span className="hint">accumulating…</span>
            )}
            {rate != null && [
              <span key="r1" className="dot">·</span>,
              <span key="r2" className="unit">burn</span>,
              <span key="r3" className="num">{rate.toFixed(2)}</span>,
              <span key="r4" className="unit">%/hr</span>,
            ]}
          </span>

          <div className="tip">
            <span className="tipHead">safe pace forecast</span>
            {safeHours != null ? [
              <span key="a1" className="tipKey">daily budget </span>,
              <span key="a2" className="tipVal good">{safeHours.toFixed(1)}h</span>,
              <span key="a3" className="tipKey"> active time per day</span>,
              "\n",
              <span key="a4" className="tipKey">for          </span>,
              <span key="a5" className="tipVal">{daysLeft ? daysLeft.toFixed(1) : "?"} days</span>,
              "\n",
              <span key="a6" className="tipKey">lands at     </span>,
              <span key="a7" className="tipVal">{target}% by weekly reset</span>,
              "\n",
            ] : <span className="tipKey">Need more active hours to compute forecast.{"\n"}</span>}
            {rate != null && [
              <span key="b1" className="tipKey">current rate </span>,
              <span key="b2" className="tipVal">{rate.toFixed(2)}% quota/active hour</span>,
              "\n",
            ]}
            <span className="tipNote">
              "Active hour" = a distinct hour where you actually sent at
              least one message. Idle time doesn't count — so 4h/day means
              4 hours of real typing, not 4 hours of wall-clock presence.
              One heavy day front-loads the rate calc; it smooths as the
              week progresses.
            </span>
          </div>
        </div>

        <span className="rule" />

        {/* TODAY — retrospective */}
        <div className="card cardInline">
          <span className="lbl">today</span>
          <span className="val">
            <span className="num">{today.active_hours || 0}</span>
            <span className="unit">h</span>
            <span className="dot">·</span>
            <span className="num">{(today.turns || 0).toLocaleString()}</span>
            <span className="unit">turns</span>
            <span className="dot">·</span>
            <span className="num">{(today.tokens_m || 0).toFixed(1)}</span>
            <span className="unit">M tok</span>
            {today.top_model && [
              <span key="m1" className="dot">·</span>,
              <span key="m2" className="hint">{today.top_model}</span>,
            ]}
            {today.top_project && [
              <span key="p1" className="dot">/</span>,
              <span key="p2" className="hint">{today.top_project}</span>,
            ]}
          </span>

          <div className="tip">
            <span className="tipHead">today · since midnight pt</span>
            <span className="tipKey">active hours </span><span className="tipVal">{today.active_hours || 0}</span>{"\n"}
            <span className="tipKey">turns        </span><span className="tipVal">{(today.turns || 0).toLocaleString()}</span>{"\n"}
            <span className="tipKey">tokens       </span><span className="tipVal">{(today.tokens_m || 0).toFixed(1)}M</span>{"\n"}
            <span className="tipKey">sessions     </span><span className="tipVal">{today.sessions || 0}</span>{"\n"}
            <span className="tipKey">top model    </span><span className="tipVal">{today.top_model || "—"}</span>{"\n"}
            <span className="tipKey">top project  </span><span className="tipVal">{today.top_project || "—"}</span>
            <span className="tipNote">
              Buckets reset at midnight Pacific (your actual workday), not UTC.
            </span>
          </div>
        </div>

        {/* EXTRA — pay-as-you-go dollar budget (monthly cap) */}
        {extra && [
          <span key="xr" className="rule" />,
          <div key="xc" className="card cardInline">
            <span className="lbl">extra $</span>
            <span className="val">
              <span className="num">${extra.used_dollars.toFixed(0)}</span>
              <span className="dot">/</span>
              <span className="hint">${extra.cap_dollars.toFixed(0)}</span>
              <span className="dot">·</span>
              <span className="num">{extra.used_pct.toFixed(0)}</span>
              <span className="unit">%</span>
              {extra.cap_hit_label ? [
                <span key="ce" className="dot">→</span>,
                <span key="ch" className={"num " + (extra.will_exhaust_before_reset ? "crit" : "warn")}>
                  cap {extra.cap_hit_label}
                </span>,
              ] : extra.pace_dollars_per_day === 0 ? [
                <span key="cs" className="dot">·</span>,
                <span key="ct" className="hint">stable</span>,
              ] : [
                <span key="cs" className="dot">·</span>,
                <span key="ct" className="hint">tracking…</span>,
              ]}
            </span>

            <div className="tip tipRight">
              <span className="tipHead">extra $ budget · monthly cap</span>
              <span className="tipKey">used      </span><span className="tipVal">${extra.used_dollars.toFixed(2)}</span>{"\n"}
              <span className="tipKey">remaining </span><span className="tipVal">${extra.remaining_dollars != null ? extra.remaining_dollars.toFixed(2) : (extra.cap_dollars - extra.used_dollars).toFixed(2)}</span>{"\n"}
              <span className="tipKey">cap       </span><span className="tipVal">${extra.cap_dollars.toFixed(2)}</span>{"\n"}
              <span className="tipKey">burn      </span><span className="tipVal">{extra.used_pct.toFixed(1)}% of monthly cap</span>{"\n"}
              {"\n"}
              {extra.pace_dollars_per_day != null ? [
                <span key="r1" className="tipKey">rate      </span>,
                <span key="r2" className="tipVal">${extra.pace_dollars_per_day.toFixed(2)}/day</span>,
                <span key="r3" className="tipKey">  over last {extra.pace_lookback_hours ? (extra.pace_lookback_hours < 48 ? extra.pace_lookback_hours.toFixed(0) + "h" : (extra.pace_lookback_hours / 24).toFixed(1) + "d") : "?"}</span>,
                "\n",
              ] : [
                <span key="r1" className="tipKey">rate      </span>,
                <span key="r2" className="tipVal">— (need more snapshot history)</span>,
                "\n",
              ]}
              {extra.cap_hit_label ? [
                <span key="c1" className="tipKey">cap hit   </span>,
                <span key="c2" className={"tipVal " + (extra.will_exhaust_before_reset ? "crit" : "warn")}>
                  {extra.cap_hit_label}
                </span>,
                <span key="c3" className="tipKey">  ({extra.days_until_cap != null ? extra.days_until_cap.toFixed(1) : "?"} days from now)</span>,
                "\n",
              ] : extra.pace_dollars_per_day === 0 ? [
                <span key="c1" className="tipKey">cap hit   </span>,
                <span key="c2" className="tipVal good">not projected</span>,
                <span key="c3" className="tipKey">  (counter stable, no recent overage)</span>,
                "\n",
              ] : [
                <span key="c1" className="tipKey">cap hit   </span>,
                <span key="c2" className="tipVal">tracking…</span>,
                <span key="c3" className="tipKey">  (waiting for counter to move)</span>,
                "\n",
              ]}
              <span className="tipNote">
                Monthly pay-as-you-go budget. The counter accrues when
                weekly Opus usage exceeds 100% of your plan allowance. The
                rate is computed from local snapshot history (15-min
                cadence), since the Anthropic API doesn't expose a reset
                date for this field.
                {extra.will_exhaust_before_reset && "\n\n⚠ PROJECTED TO HIT CAP BEFORE MONTH END at current pace."}
              </span>
            </div>
          </div>,
        ]}

      </div>

      {/* ════════════════════════════════════════════════════════════
           ROW 3 — STANDBY ACCOUNT (compact strip)
           Role-aware: shows whichever account is NOT driving Rows 1+2.
           Normal mode: standby = overflow, shows switch ETA.
           Capped mode: standby = primary, shows "resets fri 6am → switch back".
         ════════════════════════════════════════════════════════════ */}
      {standby && standby.session && (() => {
        const stbSess = standby.session || {}
        const stbWeek = standby.weekly || {}
        const stbSessQ = clamp(stbSess.used_pct || 0)
        const stbWeekQ = clamp(stbWeek.used_pct || 0)
        const stbSessLeft = stbSess.hours_left != null ? stbSess.hours_left : 0
        const stbSessEl = Math.max(0, 5 - stbSessLeft)
        const stbSessTime = clamp((stbSessEl / 5) * 100)
        const stbSessDelta = stbSessQ - stbSessTime
        const stbWeekLeft = stbWeek.hours_left != null ? stbWeek.hours_left : 0
        const stbWeekEl = Math.max(0, 168 - stbWeekLeft)
        const stbWeekTime = clamp((stbWeekEl / 168) * 100)
        const stbWeekDelta = stbWeekQ - stbWeekTime
        const stbLabel = standby.account_label || "Standby"
        const stbReset = stbWeek.reset_time_local || stbWeek.reset_label || "—"
        const stbDays = stbWeek.days_left

        if (standbyIsPrimary) {
          // ── CAPPED MODE: primary is in standby, waiting for reset ──
          const resetHours = stbWeekLeft
          const resetClass = resetHours < 4 ? "good" : resetHours < 24 ? "hint" : "hint"
          const switchBackSoon = resetHours < 2
          // Check if the ACTIVE account (overflow) is also running low.
          // weekQuotaPct comes from the active account (set above in Rows 1+2).
          const overflowHot = weekQuotaPct >= 80
          const overflowCapped = weekQuotaPct >= 95
          const onFumes = overflowHot || overflowCapped

          if (onFumes) {
            // ── FUMES MODE: both accounts running low ──
            return (
              <div className="row row2">
                <div className="card cardInline">
                  <span className="lbl warn">
                    {overflowCapped ? "both capped" : "running low"}
                  </span>
                  <span className="val">
                    <span className={overflowCapped ? "crit" : "warn"}>
                      {overflowCapped ? "▶ UPGRADE OVERFLOW" : "overflow at " + weekQuotaPct.toFixed(0) + "%"}
                    </span>
                    <span className="dot">·</span>
                    <span className="unit">primary resets</span>
                    <span className="hint">{stbReset}</span>
                    {stbDays != null && [
                      <span key="fd" className="hint"> ({stbDays.toFixed(1)}d)</span>,
                    ]}
                  </span>

                  <div className="tip">
                    <span className="tipHead">
                      {overflowCapped
                        ? "both accounts capped — action required"
                        : "overflow running low — plan ahead"}
                    </span>
                    <span className="tipKey">overflow  </span>
                    <span className={"tipVal " + (overflowCapped ? "crit" : "warn")}>
                      {weekQuotaPct.toFixed(0)}% weekly
                    </span>{"\n"}
                    <span className="tipKey">primary   </span>
                    <span className="tipVal crit">{stbWeekQ.toFixed(0)}% weekly (capped)</span>{"\n"}
                    <span className="tipKey">resets at </span>
                    <span className="tipVal">{stbReset} ({stbDays != null ? stbDays.toFixed(1) + "d" : "?"})</span>{"\n"}
                    {"\n"}
                    <span className="tipVal warn">OPTIONS — pick one:</span>{"\n"}
                    {"\n"}
                    <span className="tipVal">1. Upgrade tilloat@gmail.com</span>{"\n"}
                    <span className="tipKey">   log in at claude.ai as tilloat@gmail.com</span>{"\n"}
                    <span className="tipKey">   → Settings → Subscription → upgrade to:</span>{"\n"}
                    <span className="tipKey">     • </span><span className="tipVal">Max 5x  ($100/mo)</span><span className="tipKey"> — good for heavy weeks</span>{"\n"}
                    <span className="tipKey">     • </span><span className="tipVal">Max 20x ($200/mo)</span><span className="tipKey"> — full mirror of primary</span>{"\n"}
                    {"\n"}
                    <span className="tipVal">2. Re-enable extra usage on primary</span>{"\n"}
                    <span className="tipKey">   log in at claude.ai as your main account</span>{"\n"}
                    <span className="tipKey">   → Settings → Usage → toggle extra usage ON</span>{"\n"}
                    <span className="tipKey">   ⚠ charges at API rates ($1=$1, ~50x worse)</span>{"\n"}
                    {"\n"}
                    <span className="tipVal">3. Wait for primary reset</span>{"\n"}
                    <span className="tipKey">   primary resets {stbReset}</span>{"\n"}
                    <span className="tipKey">   use claude (not claude2) after reset</span>{"\n"}
                    <span className="tipNote">
                      The Pro plan ($20/mo) is meant as a cheap relief valve
                      for 1-2 overflow days. If you're consistently burning
                      through it, upgrading to Max 5x ($100) is 50x better
                      value than re-enabling extra usage on primary.
                    </span>
                  </div>
                </div>
              </div>
            )
          }

          // ── NORMAL CAPPED MODE: overflow still has headroom ──
          // Migration nudge: existing CC windows keep billing primary until
          // closed. Show "close old · claude2 new" front-and-center; pulse
          // when primary is genuinely over the edge (≥97%).
          const migrateUrgent = stbWeekQ >= 97
          const migrateClass = migrateUrgent ? "nudgeUrgent" : "nudge"
          return (
            <div className="row row2">
              <div className="card cardInline">
                <span className="lbl">{stbLabel.toLowerCase()} <span className="lblDim">· capped</span></span>
                <span className="val">
                  {switchBackSoon ? [
                    <span key="sb" className="good">▶ SWITCH BACK</span>,
                    <span key="sc" className="hint">claude</span>,
                    <span key="sd" className="dot">·</span>,
                  ] : [
                    <span key="mg" className={migrateClass}>▶ close windows · new:</span>,
                    <span key="mc" className={migrateClass}>claude2</span>,
                    <span key="md" className="dot">·</span>,
                    <span key="rb" className="unit">resets</span>,
                    <span key="rt" className={resetClass}>{stbReset}</span>,
                    stbDays != null && <span key="rd" className="hint">({stbDays.toFixed(1)}d)</span>,
                    <span key="re" className="dot">·</span>,
                  ]}
                  <span className="unit">wk</span>
                  <span className="crit">{stbWeekQ.toFixed(0)}%</span>
                  <span className="pbar" style={{ width: "48px" }}>
                    <span className="fillTime" style={{ width: stbWeekTime + "%" }} />
                    <span className="fillQuota bgCrit" style={{ width: stbWeekQ + "%" }} />
                  </span>
                </span>

                <div className="tip">
                  <span className="tipHead">{stbLabel} · capped, waiting for reset</span>
                  <span className="tipKey">status    </span><span className="tipVal crit">weekly cap reached ({stbWeekQ.toFixed(0)}%)</span>{"\n"}
                  <span className="tipKey">resets at </span><span className="tipVal">{stbReset}</span>{"\n"}
                  <span className="tipKey">days left </span><span className="tipVal">{stbDays != null ? stbDays.toFixed(1) : "—"}</span>{"\n"}
                  {"\n"}
                  <span className="tipVal warn">migrate now:</span>{"\n"}
                  <span className="tipKey">  1. close every open Claude Code window</span>{"\n"}
                  <span className="tipKey">     (existing windows keep billing primary)</span>{"\n"}
                  <span className="tipKey">  2. open a new terminal tab</span>{"\n"}
                  <span className="tipKey">  3. type </span><span className="tipVal">claude2</span><span className="tipKey"> (not claude)</span>{"\n"}
                  <span className="tipKey">  4. repeat step 2–3 per window you need</span>{"\n"}
                  {"\n"}
                  <span className="tipKey">when it resets:</span>{"\n"}
                  <span className="tipKey">  1. open a new terminal tab</span>{"\n"}
                  <span className="tipKey">  2. type </span><span className="tipVal">claude</span><span className="tipKey"> (not claude2)</span>{"\n"}
                  <span className="tipKey">  3. primary Max 20x allotment is back</span>{"\n"}
                  <span className="tipNote">
                    The primary account resets to 0% weekly usage at
                    the time shown above. Once it resets, switch back
                    to save the Pro overflow for next week's cap.
                  </span>
                </div>
              </div>
            </div>
          )
        }

        // ── NORMAL MODE: overflow is in standby ──
        const capEta = standby.primary_cap_eta
        const capLabel = capEta ? capEta.label : null
        const capHours = capEta ? capEta.hours : null
        const willCap = capEta ? capEta.will_cap : false
        // Urgency: <12h = imminent (amber), <4h = critical (white underline)
        const capClass = capHours == null ? "hint"
          : capHours < 4 ? "crit"
          : capHours < 12 ? "warn"
          : "good"
        return (
          <div className="row row2">
            <div className="card cardInline">
              <span className="lbl">{stbLabel.toLowerCase()} <span className="lblDim">· overflow</span></span>
              <span className="val">
                {willCap && capLabel ? [
                  <span key="sw" className="unit">switch</span>,
                  <span key="sl" className={capClass}>~{capLabel}</span>,
                  capHours != null && <span key="sh" className="hint">({capHours < 24 ? capHours.toFixed(0) + "h" : (capHours / 24).toFixed(1) + "d"})</span>,
                  <span key="sd" className="dot">·</span>,
                ] : [
                  <span key="ns" className="hint">no switch needed</span>,
                  <span key="nd" className="dot">·</span>,
                ]}
                <span className="unit">sess</span>
                <span className={paceClass(stbSessDelta)}>{stbSessQ.toFixed(0)}%</span>
                <span className="pbar" style={{ width: "48px" }}>
                  <span className="fillTime" style={{ width: stbSessTime + "%" }} />
                  <span className={"fillQuota " + paceBgClass(stbSessDelta)} style={{ width: stbSessQ + "%" }} />
                </span>
                <span className="dot">·</span>
                <span className="unit">wk</span>
                <span className={paceClass(stbWeekDelta)}>{stbWeekQ.toFixed(0)}%</span>
                <span className="pbar" style={{ width: "48px" }}>
                  <span className="fillTime" style={{ width: stbWeekTime + "%" }} />
                  <span className={"fillQuota " + paceBgClass(stbWeekDelta)} style={{ width: stbWeekQ + "%" }} />
                </span>
                {stbDays != null && [
                  <span key="od" className="dot">·</span>,
                  <span key="on" className="num">{stbDays.toFixed(1)}</span>,
                  <span key="ou" className="unit">d left</span>,
                ]}
                <span className="dot">·</span>
                <span className="hint">{stbReset}</span>
              </span>

              <div className="tip">
                <span className="tipHead">{stbLabel} · overflow account</span>
                {willCap && capLabel ? [
                  <span key="e1" className="tipKey">switch at </span>,
                  <span key="e2" className={"tipVal " + capClass}>~{capLabel}</span>,
                  <span key="e3" className="tipKey">  ({capHours != null ? (capHours < 24 ? capHours.toFixed(1) + "h" : (capHours / 24).toFixed(1) + "d") : "?"} from now)</span>,
                  "\n",
                  <span key="e4" className="tipKey">primary   </span>,
                  <span key="e5" className="tipVal">burning {capEta.rate_pct_per_hour.toFixed(2)}%/hr → hits 100% before reset</span>,
                  "\n",
                  <span key="e6" className="tipKey">command   </span>,
                  <span key="e7" className="tipVal">claude2</span>,
                  <span key="e8" className="tipKey">  (new terminal tab when the time comes)</span>,
                  "\n",
                ] : [
                  <span key="e1" className="tipKey">switch at </span>,
                  <span key="e2" className="tipVal good">not projected — primary won't cap this week</span>,
                  "\n",
                ]}
                <span className="tipKey">session   </span><span className={"tipVal " + paceClass(stbSessDelta)}>{stbSessQ.toFixed(0)}% used</span>{"\n"}
                <span className="tipKey">weekly    </span><span className={"tipVal " + paceClass(stbWeekDelta)}>{stbWeekQ.toFixed(0)}% used</span>{"\n"}
                <span className="tipKey">days left </span><span className="tipVal">{stbDays != null ? stbDays.toFixed(1) : "—"}</span>{"\n"}
                <span className="tipKey">resets at </span><span className="tipVal">{stbReset}</span>
                <span className="tipNote">
                  Switch to claude2 when the primary account hits its weekly
                  cap. This account absorbs the overflow at subscription
                  rates (~50x better value than extra usage overage).
                  {"\n\n"}alias: claude2='CLAUDE_CONFIG_DIR=~/.claude-alt claude'
                </span>
              </div>
            </div>
          </div>
        )
      })()}

    </div>
  )
}
