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
const PYTHON_BIN = "$HOME/Desktop/code/kicksaw/venv_kicksaw/bin/python3"
const REPO_ROOT  = "$HOME/Desktop/code/_local_infrastructure/cc_usage"

// Übersicht 1.6 exposes `run(cmd)` via the `uebersicht` module — NOT as a
// global. Importing here makes onClick handlers in the JSX able to fire
// shell commands (e.g. the macBtn that launches smart_mac_cleaner).
import { run } from "uebersicht"

// Overflow account (claude2) renewal date. Set on 2026-04-15 when it was
// upgraded Pro → Max 20x. On 2026-04-26 the decision was made to downgrade
// back to Pro — confirmed by one heavy week (57% of Max 20x, primary
// capped) followed by two near-zero weeks (4% and 3%). claude2 stays Max
// 20x through 2026-05-14, then auto-converts to Pro on 2026-05-15. Pro
// covers a typical overflow week (~3–4% of Max 20x ≈ 60–80% of Pro) but
// CANNOT cover a real cap week — if primary caps post-downgrade, bump
// claude2 back to Max via Settings → Billing → Adjust plan. Stays as
// warm spare otherwise.
//
// NOTE for future edits: tooltips below that say "Both accounts are Max
// 20x" are correct only through 2026-05-14. After May 15, claude2 is
// Pro ($20/mo, ~1/20 the weekly allotment) — capped-mode advice changes
// (overflow exhausts in hours, not days) and the "$10k API-equivalent"
// framing no longer applies.
const OVERFLOW_RENEWAL_DATE = "2026-05-14"
const OVERFLOW_DOWNGRADE_SCHEDULED = true   // → Pro on 2026-05-15
const renewalDaysLeft = () => {
  const now = new Date()
  const renewal = new Date(OVERFLOW_RENEWAL_DATE + "T07:00:00Z") // approx midnight PT
  return Math.ceil((renewal - now) / (1000 * 60 * 60 * 24))
}

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

  /* Click-to-run mac cleaner button — in row 2 when load is bad. */
  .macBtn {
    cursor: pointer;
    padding: 0 6px;
    border-radius: 3px;
    border: 1px solid currentColor;
    transition: background 100ms ease;
  }
  .macBtn:hover { background: rgba(255, 184, 0, 0.18); }
  .macBtn:active { background: rgba(255, 184, 0, 0.32); }

  /* Live-session inline wrapper — one per active session in the LIVE card. */
  .liveSess {
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  /* ═══ WINDOWS STRIP — horizontal banner of active Claude Code windows ═══
     Shows each live window's context fill against the 1M context beta, so
     the user can eyeball "how close to the ceiling am I on each open
     project" at a glance. Distinct from the row-2 LIVE card (which frames
     sessions in terms of $/reply cost bands) — this one is purely a ceiling
     meter. Sorted by fill %, worst-first. */
  .winStrip {
    border-bottom: 1px solid rgba(74, 227, 255, 0.10);
    height: 20px;
    padding: 0 18px;
    gap: 14px;
    overflow: hidden;
  }
  .winStripLbl {
    font-size: 8.5px;
    font-weight: 800;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #4AE3FF;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .winStripLblDim { color: #5A6B82; font-weight: 600; }
  .win {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: "SF Mono", ui-monospace, "JetBrains Mono", "Menlo", monospace;
    font-size: 10px;
    font-weight: 500;
    color: #FFFFFF;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    letter-spacing: -0.005em;
  }
  .winName {
    color: #B8C8E0;
    font-weight: 600;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .winBar {
    display: inline-block;
    position: relative;
    width: 44px;
    height: 6px;
    background-color: rgba(184, 200, 224, 0.07);
    background-image: linear-gradient(
      to right,
      transparent 0,
      transparent calc(50% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(50% - 0.5px),
      rgba(184, 200, 224, 0.26) calc(50% + 0.5px),
      transparent calc(50% + 0.5px),
      transparent 100%
    );
    border-top: 1px solid rgba(184, 200, 224, 0.28);
    border-bottom: 1px solid rgba(184, 200, 224, 0.28);
    flex-shrink: 0;
    vertical-align: middle;
  }
  .winBarFill {
    position: absolute;
    top: 0; left: 0; bottom: 0;
  }
  .winK {
    font-weight: 700;
    color: #FFFFFF;
  }
  .winPct {
    font-weight: 700;
    font-size: 9.5px;
  }
  .winFlag {
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 1px 4px 0 4px;
    border: 1px solid currentColor;
    line-height: 1;
  }
  .winRule {
    width: 1px;
    height: 10px;
    background: rgba(184, 200, 224, 0.18);
    flex-shrink: 0;
  }
  .winCost {
    font-size: 9px;
    font-weight: 600;
    color: #8FA3BF;
    font-variant-numeric: tabular-nums;
  }
  .winAgents {
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.04em;
    color: #B589FF;
    padding: 1px 4px 0 4px;
    border: 1px solid currentColor;
    line-height: 1;
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
  .contribStrip { margin-top: 2px; }
  .contribBand {
    display: inline-flex;
    align-items: baseline;
    gap: 3px;
    margin-left: 9px;
    letter-spacing: 0.04em;
  }
  .contribLbl { font-size: 9px; opacity: 0.65; text-transform: uppercase; }
  .contribPct { font-size: 11px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .contribDim  .contribPct { color: rgba(184, 200, 224, 0.55); }
  .contribWarn .contribPct { color: #FFC857; }
  .contribDom  .contribPct { color: #FF6B9D; text-decoration: underline; text-underline-offset: 2px; }
  .contribDom  .contribLbl { opacity: 0.95; color: #FF6B9D; }
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

  /* ═══ stale anchor (snapshot poller dead/lagging) ═══
     Subtle, never a red error splash and never a freeze (per widget failure
     policy). The numbers still paint — they're just visibly de-trusted: the
     primary clocks dim and the "updated" stamp becomes an amber "⟳ stale Nh"
     tag. Catches the 2026-05-11 class of silent rot where the extrapolation
     rode a 19-day-old calibration anchor and showed a confident, wrong %. */
  .bar.stale .num { opacity: 0.4; }
  .bar.stale .pulse { background: #E0A23C; box-shadow: 0 0 6px #E0A23C; animation: none; }
  .updated.staleUpd { color: #E0A23C; }
  .staleTag {
    color: #E0A23C;
    font-weight: 700;
    letter-spacing: 0.03em;
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

  /* ═══ Session cap alert ═══
     Fires when the 5h session will hit 100% (≥90% used OR projected to cap
     before the window resets — whichever first). Red, pulsing "⚠ CAPS IN Nm"
     so a heads-down user catches it on a glance. In-widget only by design. */
  .capAlert {
    color: #FF5A5A;
    font-family: "SF Mono", ui-monospace, "JetBrains Mono", monospace;
    font-weight: 800;
    letter-spacing: 0.02em;
    animation: cc-nudge 1.2s ease-in-out infinite;
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
  // Swap only if primary is truly capped AND there's >24h until reset.
  // claude2 is a warm spare, not a daily driver — so when primary is at the
  // threshold with hours left to reset, ride primary to ground instead of
  // promoting an idle overflow card that reads as zeros.
  const primaryWeekPct = (primary.weekly || {}).used_pct || 0
  const primaryHoursLeft = (primary.weekly || {}).hours_left || 0
  const primaryCapped = primaryWeekPct >= 99 && primaryHoursLeft > 24
  const hasOverflow = overflow && overflow.session
  const active = (primaryCapped && hasOverflow) ? overflow : primary
  const standby = (primaryCapped && hasOverflow) ? primary : overflow
  const activeLabel = active.account_label || "Max 20x"
  const standbyIsPrimary = primaryCapped && hasOverflow

  // ── anchor staleness ──
  // Python sets active.stale=true when the newest snapshot (the calibration
  // anchor the extrapolation rides on) is older than 90 min — i.e. the
  // launchd poller has likely died. We dim the numbers and swap the "updated"
  // stamp for a "⟳ stale Nh" tag so a dead poller can't masquerade as a live
  // reading (the 2026-05-11 silent-rot incident). NOT a red error, NOT a
  // freeze — the numbers still render, just visibly de-trusted.
  const activeStale = !!active.stale
  const staleSec = active.anchor_age_sec || 0
  const staleAgeLabel = staleSec >= 3600
    ? Math.floor(staleSec / 3600) + "h"
    : Math.max(1, Math.floor(staleSec / 60)) + "m"

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

  // Weekly burn trend — "how hot am I running vs my own history". Bars are
  // cost-weighted token burn (comparable across the SpaceX limit change, unlike
  // quota %). Current (partial) week is highlighted; "heat" compares it to the
  // median of prior complete weeks.
  const weekTrend = Array.isArray(weekly.trend) ? weekly.trend : []
  const maxWeekEff = Math.max(1, ...weekTrend.map((w) => w.eff_mtok || 0))
  const curWeek = weekTrend.find((w) => w.is_current)
  const priorEff = weekTrend.filter((w) => !w.is_current && (w.eff_mtok || 0) > 0)
    .map((w) => w.eff_mtok).sort((a, b) => a - b)
  const typicalEff = priorEff.length ? priorEff[Math.floor(priorEff.length / 2)] : 0
  const heatRatio = (curWeek && typicalEff) ? curWeek.eff_mtok / typicalEff : null
  const heatWord = heatRatio == null ? "" : heatRatio >= 1.25 ? "hot" : heatRatio >= 0.8 ? "typical" : "light"
  const heatCls = heatRatio == null ? "hint" : heatRatio >= 1.25 ? "warn" : heatRatio >= 0.8 ? "num" : "good"

  // Utilization gauge — "am I getting my $200's worth?". COLD = leaving the plan
  // unused (amber nudge to spin up more windows/ultracode); on-target = using it
  // well; HOT = projected past 99% → overage ($) risk. headroom_x = how much
  // harder you could run for the rest of the week and still just hit target.
  const headroomX = weekly.headroom_x
  const utilStatus = weekly.utilization_status   // cold | warm | on-target | hot
  // headroomX/utilStatus are now built on the DAMPED pace estimate (server side),
  // not the raw early-week projection, so they stop whipsawing. paceLowConf marks
  // the pre-Wed window where the linear read can't be trusted yet → render a `*`.
  const paceLowConf = weekly.pace_low_conf
  // The stable primary action number: daily allowance + today's burn against it.
  // "you can spend ~X%/day and still land at target; today you're at Y% → N× left."
  // Unaffected by the projection swing or a mid-week re-baseline.
  const safePerDay = weekly.safe_pct_per_day
  const todayPct = weekly.today_pct
  const todayRoomX = weekly.today_room_x
  // Set when Anthropic zeroed the weekly counter mid-window without moving its
  // reset boundary (a server-side re-baseline, observed 2026-06-01). Surfaced
  // so a discontinuous COLD jump in headroom is EXPLAINED, not mysterious.
  const rebaselinedAt = weekly.rebaselined_at
  const rebaseLabel = rebaselinedAt
    ? new Date(rebaselinedAt).toLocaleTimeString("en-US",
        { hour: "numeric", minute: "2-digit" })
    : null
  const utilCls = utilStatus === "cold" ? "warn"
    : utilStatus === "hot" ? "crit"
    : utilStatus === "on-target" ? "good" : "num"

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

  // ── windows strip (context fill of 1M context beta) ──
  // Re-rank the active sessions by fill %, worst-first, and tag each one
  // with a threshold class. These thresholds are tied to the 1M ceiling,
  // not the 280k $/reply bands — two different questions, two different
  // displays.
  const CONTEXT_CAP = 1_000_000
  const winSorted = liveSessions
    .map((s) => {
      const ctx = s.context_tokens || 0
      const pct = (ctx / CONTEXT_CAP) * 100
      // Tuned to cost-per-turn, not auto-compact. At ≥40% fill (400k ctx)
      // cost-per-turn climbs noticeably; ≥65% (650k) is the last comfortable
      // handoff window before things get expensive AND slow.
      const cls = pct >= 65 ? "crit" : pct >= 40 ? "warn" : "good"
      const flag = pct >= 65 ? "⚠ handoff" : null
      return { ...s, _pct: pct, _cls: cls, _flag: flag }
    })
    .sort((a, b) => b._pct - a._pct)

  return (
    <div className={"bar" + (activeStale ? " stale" : "")}>

      {/* ════════════════════════════════════════════════════════════
           ROW 0 — WINDOWS STRIP (context fill of 1M)
           Horizontal list of every currently-active Claude Code window
           with a mini fill bar against the 1M context ceiling. Tells the
           user which window is about to hit auto-compact so they can
           /handoff on their own terms instead of letting the summary do it.
         ════════════════════════════════════════════════════════════ */}
      {winSorted.length > 0 && (
        <div className="row winStrip">
          <span className="winStripLbl">
            windows <span className="winStripLblDim">· ctx of 1M</span>
          </span>
          {winSorted.map((s, i) => (
            <span key={s.session_id || i} className="win">
              {i > 0 && <span className="winRule" />}
              <span className="winName">{s.project || "?"}</span>
              <span className="winBar">
                <span
                  className={"winBarFill " + (s._cls === "crit" ? "bgCrit" : s._cls === "warn" ? "bgWarn" : "bgGood")}
                  style={{ width: Math.min(100, s._pct).toFixed(1) + "%" }}
                />
              </span>
              <span className="winK">
                {s.context_k != null ? (s.context_k >= 100 ? s.context_k.toFixed(0) : s.context_k.toFixed(1)) : "—"}k
              </span>
              <span className={"winPct " + s._cls}>{s._pct.toFixed(0)}%</span>
              {s.cost_per_reply_usd != null && s.cost_per_reply_usd > 0 && (
                <span className="winCost">${s.cost_per_reply_usd.toFixed(2)}/r</span>
              )}
              {s.agents_active && (
                <span className="winAgents" title={"workflow / subagent fan-out — " + s.agent_turns + " agent turns" + (s.agent_types && s.agent_types.length ? " (" + s.agent_types.join(", ") + ")" : "")}>⚙ {s.agent_turns}</span>
              )}
              {s._flag && <span className={"winFlag " + s._cls}>{s._flag}</span>}
            </span>
          ))}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
           ROW 1 — PRIMARY CLOCKS
           [CC · TARGET]  │  [SESSION 5H]  │  [WEEK 168H]  │  [updated]
         ════════════════════════════════════════════════════════════ */}
      <div className="row">

        {/* IDENTITY — leads with the $ gate, the constraint that actually binds
            post-SpaceX (May 2026 limit increases made weekly quota non-scarce —
            primary now projects ~19% on a hard week). The dollar overage cap is
            the real ceiling now, so it gets top billing here; the WEEK quota card
            to the right keeps the pacing detail. Falls back to the quota target
            when there's no extra-usage payload (credits off / overflow active). */}
        <div className="card">
          <span className="lbl lblDim">claude code{standbyIsPrimary && active.account_tier === "pro" ? " · pro" : ""}</span>
          <span className="val">
            {extra ? [
              <span key="d" className="num">${extra.used_dollars.toFixed(0)}</span>,
              <span key="sl" className="dot">/</span>,
              <span key="cap" className="hint">${extra.cap_dollars.toFixed(0)}</span>,
              <span key="mid" className="dot">·</span>,
              <span key="pct" className={"num " + (extra.will_exhaust_before_reset ? "crit" : "")}>{extra.used_pct.toFixed(0)}</span>,
              <span key="u" className="unit">%</span>,
              extra.cap_hit_label && <span key="cd" className="dot">→</span>,
              extra.cap_hit_label && <span key="cl" className={extra.will_exhaust_before_reset ? "crit" : "hint"}>cap {extra.cap_hit_label.split(",")[0]}</span>,
            ] : [
              <span key="t" className="num">{target}</span>,
              <span key="tu" className="unit">%</span>,
              <span key="th" className="hint">target</span>,
            ]}
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
            {/* Cap alert — when you hit the wall, and what happens then. Red +
               pulsing; in-widget only (no OS popup). Before cap: minutes of work
               left + how long you'd sit blocked. AT cap: if usage credits are ON
               (extra present), you're NOT blocked — you're billing overage at
               standard API rates, so show the live month-to-date extra spend.
               If credits are OFF, you're blocked until the 5h reset. Verified
               2026-06-01: extra usage triggers at the 5h SESSION limit. */}
            {session.cap_alert && session.caps_in_min != null && [
              <span key="cad" className="dot">·</span>,
              <span key="cap" className="capAlert">
                {session.caps_in_min <= 0
                  ? (extra
                      ? "⚠ AT CAP · billing extra $" + extra.used_dollars.toFixed(2)
                      : "⚠ AT CAP · blocked till " + sessReset)
                  : "⚠ CAPS IN " + session.caps_in_min + "m"
                    + (session.will_cap_before_reset && session.cap_before_reset_min != null
                        ? " (" + session.cap_before_reset_min + "m before reset)"
                        : "")
                    + (extra ? " → then extra $" : "")}
              </span>,
            ]}
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
            {/* Utilization gauge replaces the old "running hot" pacing: post-SpaceX
               the goal is to USE the $200 plan, not avoid the cap. COLD nags you to
               run more; HOT warns of overage. */}
            {utilStatus && [
              <span key="ud" className="dot">·</span>,
              <span key="us" className={utilCls}>{utilStatus}</span>,
              headroomX != null && utilStatus !== "on-target" && (
                <span key="ux" className="hint" title={paceLowConf
                  ? "pace estimate — LOW CONFIDENCE until ~Wed. Early-week the live projection swings wildly (and a mid-week re-baseline craters it), so this is damped toward your average daily burn so far. It firms up as the week elapses."
                  : "how much harder you could run for the rest of the week and still just land at target, off the damped pace estimate"}
                >~{headroomX}× room{paceLowConf ? "*" : ""}</span>
              ),
              // Stable allowance — the primary "how much can I use right now".
              safePerDay != null && [
                <span key="bd2" className="dot">·</span>,
                <span key="bg" className="num" title="DAILY ALLOWANCE — how much of your weekly quota you can spend each remaining day and still land at target. Stable: unaffected by the early-week projection swing or a re-baseline (a re-baseline just raises it).">{safePerDay.toFixed(0)}%/day</span>,
              ],
              todayPct != null && todayRoomX != null && [
                <span key="td" className="dot">·</span>,
                <span key="tt" className="hint" title="today's burn vs the daily allowance — how much more of today's pace you could still run">today {todayPct.toFixed(0)}% ({todayRoomX}× left)</span>,
              ],
              rebaseLabel && (
                <span key="rb" className="hint" title={"Anthropic re-baselined the weekly counter at " + rebaseLabel + " (reset boundary unchanged) — the swing you saw was an artifact; the daily allowance is the number to trust"}>↺ {rebaseLabel}</span>
              ),
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

        {/* EXTRA $ — pay-as-you-go monthly overage budget. Re-added 2026-06-01
            (removed 2026-05-30 in 3d397ef, which moved a compact $ to the identity
            "gate" but dropped the $/day pace + projected cap-hit detail). Kept
            ALONGSIDE the gate per Andy's call: gate = glanceable, this card =
            hover for the pacing instrument. */}
        {extra && [
          <span key="xr" className="rule" />,
          <div key="xc" className="card cardInline">
            <span className="lbl">extra $</span>
            <span className="val">
              <span className="num">${extra.used_dollars.toFixed(0)}</span>
              <span className="dot">/</span>
              <span className="hint">${extra.cap_dollars.toFixed(0)}</span>
              <span className="dot">·</span>
              <span className={"num " + (extra.will_exhaust_before_reset ? "crit" : "")}>{extra.used_pct.toFixed(0)}</span>
              <span className="unit">%</span>
              {extra.cap_hit_label ? [
                <span key="ce" className="dot">→</span>,
                <span key="ch" className={"num " + (extra.will_exhaust_before_reset ? "crit" : "warn")}>cap {extra.cap_hit_label.split(",")[0]}</span>,
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
                <span key="c2" className={"tipVal " + (extra.will_exhaust_before_reset ? "crit" : "warn")}>{extra.cap_hit_label}</span>,
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
                Month-to-date usage-credit spend (resets monthly). Accrues
                when you hit your 5-HOUR SESSION limit with credits ON and
                keep working — billed at standard API rates. NOT tied to the
                weekly limit. Drawn from your prepaid balance first; the API
                doesn't expose that balance, so this shows spend vs your
                ${extra.cap_dollars.toFixed(0)} monthly cap. Rate computed
                from local snapshot history (15-min cadence), so it can lag
                the live spend by up to one poll.
                {extra.will_exhaust_before_reset && "\n\n⚠ PROJECTED TO HIT CAP BEFORE MONTH END at current pace."}
              </span>
            </div>
          </div>,
        ]}

        <span className={"updated" + (activeStale ? " staleUpd" : "")}>
          <span className="pulse" />
          {activeStale
            ? <span className="staleTag" title={"snapshot poller stale — last anchor " + staleAgeLabel + " ago; numbers extrapolated off an old calibration point"}>⟳ stale {staleAgeLabel}</span>
            : <span>{d.updated_pt || primary.updated_pt || "—"}</span>}
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

        {/* WEEKS — 8-week burn trend (cost-weighted). "How hot vs my usual." */}
        {weekTrend.length > 0 && [
          <span key="wkrule" className="rule" />,
          <div key="wkcard" className="card cardInline">
            <span className="lbl">weeks</span>
            <span className="spark">
              {weekTrend.map((w) => {
                const pct = ((w.eff_mtok || 0) / maxWeekEff) * 100
                const barH = (w.eff_mtok || 0) > 0 ? Math.max(2, (pct / 100) * 12) : null
                return (
                  <span key={w.week_end} className="sparkCell">
                    <span className={"sparkLabel " + (w.is_current ? "sparkLabelToday" : "")}>
                      {(w.week_end.split("/")[1] || "")}
                    </span>
                    {barH != null ? (
                      <span
                        className={"sparkBar " + (w.is_current ? "sparkBarToday" : "")}
                        style={{ height: barH + "px" }}
                      />
                    ) : <span className="sparkEmpty" />}
                  </span>
                )
              })}
            </span>
            {heatWord && [
              <span key="hw" className="dot">·</span>,
              <span key="hv" className={heatCls}>{heatWord}</span>,
              heatRatio != null && <span key="hr" className="hint">{heatRatio.toFixed(1)}× median</span>,
            ]}

            <div className="tip">
              <span className="tipHead">weekly burn trend · cost-weighted</span>
              {weekTrend.map((w) => {
                const mark = w.is_current ? "●" : " "
                const pk = w.peak_pct != null ? w.peak_pct + "%" : "—"
                return (
                  <span key={w.week_end}>
                    <span className={w.is_current ? "tipVal good" : "tipKey"}>
                      {mark} {String(w.week_end).padStart(5)}  {String(w.eff_mtok).padStart(5)} eff  {String(w.turns.toLocaleString()).padStart(6)}t  peak {pk.padStart(4)}
                    </span>
                    {"\n"}
                  </span>
                )
              })}
              <span className="tipNote">
                Bar = cost-weighted token burn that week (output 5×, cache-read
                0.1×) — a limit-independent "how hard did I run" gauge. Quota %
                isn't comparable across the May SpaceX limit increase, so burn is
                the honest trend. "peak %" is the authoritative snapshot max where
                the poller had data (— = gap, e.g. the 5/11–5/30 outage).
              </span>
            </div>
          </div>,
        ]}

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


      </div>

      {/* ════════════════════════════════════════════════════════════
           ROW 2.5 — BURN CONTRIBUTORS (last 24h)
           Mirrors `claude /usage` "what's contributing" panel. Helps
           decide when to /handoff (high ctx), close windows (parallel),
           or cheaper-model the subagents (subagent-heavy).
         ════════════════════════════════════════════════════════════ */}
      {active.contributors && (() => {
        const c = active.contributors
        const bands = [
          { key: "ctx",   lbl: "ctx>150k", pct: c.ctx_over_150k_pct, hint: "→ /handoff or /compact",       warn: 60 },
          { key: "long",  lbl: "8h+ sess", pct: c.long_session_pct,  hint: "→ /handoff long sessions",     warn: 60 },
          { key: "par",   lbl: "∥4+ par",  pct: c.parallel_pct,      hint: "→ close idle windows",         warn: 30 },
          { key: "sub",   lbl: "subagent", pct: c.subagent_pct,      hint: "→ cheaper model for subagents", warn: 25 },
        ].filter(b => b.key === "ctx" || b.pct > 0)   // keep ctx always (the real lever); drop 0% noise
        const dominantPct = Math.max(...bands.map(b => b.pct))
        return (
          <div className="row row2 contribStrip">
            <div className="card cardInline">
              <span className="lbl">contrib · 24h</span>
              {bands.map(b => {
                const isDom = b.pct === dominantPct && b.pct > 0
                const isWarn = b.pct >= b.warn
                const cls = isDom ? "contribDom" : isWarn ? "contribWarn" : "contribDim"
                return (
                  <span key={b.key} className={"contribBand " + cls}>
                    <span className="contribLbl">{b.lbl}</span>
                    <span className="contribPct">{b.pct}%</span>
                  </span>
                )
              })}
              <div className="tip">
                <span className="tipHead">what's burning your week (last 24h)</span>
                {bands.map(b => [
                  <span key={b.key + "k"} className="tipKey">{b.lbl} </span>,
                  <span key={b.key + "v"} className="tipVal">{b.pct}%</span>,
                  <span key={b.key + "h"} className="tipKey">  {b.hint}</span>,
                  "\n",
                ])}
                <span className="tipNote">
                  Cost-weighted share of last 24h burn. Bands aren't
                  mutually exclusive — a session can be long AND parallel
                  AND high-context all at once. The dominant band is the
                  cheapest lever to pull first.
                </span>
              </div>
            </div>
          </div>
        )
      })()}

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
                      {overflowCapped ? "▶ BOTH CAPPED — WAIT OR PAY" : "overflow at " + weekQuotaPct.toFixed(0) + "%"}
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
                    <span className="tipVal">1. Wait for whichever resets first</span>{"\n"}
                    <span className="tipKey">   primary resets {stbReset}</span>{"\n"}
                    <span className="tipKey">   switch back with </span><span className="tipVal">claude</span><span className="tipKey"> after reset</span>{"\n"}
                    {"\n"}
                    <span className="tipVal">2. Re-enable extra usage (last resort)</span>{"\n"}
                    <span className="tipKey">   pick whichever account resets sooner</span>{"\n"}
                    <span className="tipKey">   → Settings → Usage → toggle extra usage ON</span>{"\n"}
                    <span className="tipKey">   ⚠ charges at API rates ($1=$1, ~50x worse</span>{"\n"}
                    <span className="tipKey">     than subscription tokens)</span>{"\n"}
                    <span className="tipNote">
                      Both accounts are Max 20x ($200/mo). When both are
                      capped you've used ~$10k of API-equivalent value
                      that week — extra usage from here is pure overage
                      and best avoided unless the work truly can't wait.
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
                  <span className="hint">claude</span>
                  <span className="crit">{stbWeekQ.toFixed(2)}%</span>
                  <span className="pbar" style={{ width: "40px" }}>
                    <span className="fillTime" style={{ width: stbWeekTime + "%" }} />
                    <span className="fillQuota bgCrit" style={{ width: stbWeekQ + "%" }} />
                  </span>
                  <span className="dot">│</span>
                  <span className="hint">claude2</span>
                  <span className={paceClass(weekDelta)}>{weekQuotaPct.toFixed(2)}%</span>
                  <span className="pbar" style={{ width: "40px" }}>
                    <span className="fillTime" style={{ width: weekTimePct + "%" }} />
                    <span className={"fillQuota " + paceBgClass(weekDelta)} style={{ width: weekQuotaPct + "%" }} />
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
                    to keep the overflow's Max 20x allotment in reserve
                    for next week's cap.
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
            {/* overflow collapsed to a dim one-liner — post-SpaceX it's a Pro
               emergency spare, not a daily driver (see CLAUDE.md account-tiers).
               The capped-mode bridge branch above is intentionally untouched. */}
            <div className="card cardInline">
              <span className="lbl lblDim">{stbLabel.toLowerCase()} <span className="lblDim">· spare</span></span>
              <span className="val">
                <span className="hint">Pro · emergency only</span>
                <span className="dot">·</span>
                <span className="unit">sess</span>
                <span className={paceClass(stbSessDelta)}>{stbSessQ.toFixed(0)}%</span>
                <span className="dot">·</span>
                <span className="unit">wk</span>
                <span className="hint">{stbWeekQ.toFixed(0)}%</span>
              </span>
            </div>

            {d.mac && (() => {
              const m = d.mac
              const bandClass =
                m.band === "crit" ? "crit"
                : m.band === "warn" ? "warn"
                : m.band === "elevated" ? "warn"
                : "num"
              const showButton = m.band === "warn" || m.band === "crit"
              return (
                <div className="card cardInline macCard">
                  <span className="lbl">mac</span>
                  <span className="val">
                    <span className={bandClass}>load {m.load_1min != null ? m.load_1min.toFixed(1) : "?"}</span>
                    {m.cores != null && (
                      <span className="hint">/{m.cores}c</span>
                    )}
                    {(m.band === "elevated" || m.band === "warn" || m.band === "crit") && [
                      <span key="hd" className="dot">·</span>,
                      <span key="hh" className={m.hot_count >= 10 ? "warn" : "num"}>{m.hot_count} hot</span>,
                    ]}
                    {m.top_name && m.top_pct >= 50 && [
                      <span key="td" className="dot">·</span>,
                      <span key="tu" className="unit">top</span>,
                      <span key="tv" className={
                        m.top_pct >= 200 ? "crit"
                        : m.top_pct >= 100 ? "warn"
                        : "num"
                      }>
                        {String(m.top_name).slice(0, 14)} {m.top_pct.toFixed(0)}%
                      </span>,
                    ]}
                    {m.ram_used_pct != null && [
                      <span key="rd" className="dot">·</span>,
                      <span key="ru" className="unit">ram</span>,
                      <span key="rv" className={m.ram_used_pct >= 90 ? "warn" : "num"}>
                        {m.ram_used_pct.toFixed(0)}%
                      </span>,
                    ]}
                    {showButton && [
                      <span key="cd" className="dot">·</span>,
                      <span
                        key="cb"
                        className={"macBtn " + (m.band === "crit" ? "crit" : "warn")}
                        onClick={() => {
                          try {
                            run("$HOME/Desktop/code/_local_infrastructure/mac_cleaner/run_in_terminal.sh")
                          } catch (e) { /* keep widget alive */ }
                        }}
                        title="Click to launch smart_mac_cleaner.py in a new Terminal tab"
                      >
                        ▶ run smart_mac_cleaner
                      </span>,
                    ]}
                  </span>

                  <div className="tip tipRight">
                    <span className="tipHead">mac vitals · live</span>
                    <span className="tipKey">load 1m   </span>
                    <span className={"tipVal " + bandClass}>
                      {m.load_1min != null ? m.load_1min.toFixed(2) : "—"}
                    </span>
                    <span className="tipKey">  / {m.cores} cores</span>{"\n"}
                    <span className="tipKey">band      </span>
                    <span className={"tipVal " + bandClass}>{m.band}</span>{"\n"}
                    <span className="tipKey">hot procs </span>
                    <span className={"tipVal " + (m.hot_count >= 10 ? "warn" : "")}>{m.hot_count}</span>
                    <span className="tipKey">  (>10% CPU)</span>{"\n"}
                    <span className="tipKey">ram       </span>
                    <span className={"tipVal " + (m.ram_used_pct >= 90 ? "warn" : "")}>
                      {m.ram_used_pct != null ? m.ram_used_pct.toFixed(0) + "%" : "—"}
                    </span>
                    {m.ram_used_gb != null && m.ram_total_gb != null && (
                      <span className="tipKey">  ({m.ram_used_gb} / {m.ram_total_gb} GB)</span>
                    )}{"\n\n"}
                    <span className="tipKey">— top CPU processes —</span>{"\n"}
                    {(m.top_procs || []).map((p, i) => [
                      <span key={"pn" + i} className={
                        p.pct >= 200 ? "tipVal crit"
                        : p.pct >= 100 ? "tipVal warn"
                        : "tipVal"
                      }>
                        {(i + 1) + ". " + p.name.padEnd(28)}
                      </span>,
                      <span key={"pp" + i} className="tipKey">{p.pct.toFixed(1) + "%"}</span>,
                      "\n",
                    ])}
                    <span className="tipNote">
                      load = work-queue depth (best signal). Above {m.cores} = busy,
                      above {m.cores * 2} = sweating, above {m.cores * 4} = overwhelmed.
                      {showButton ? "\n\nClick the ▶ button to fix." : ""}
                    </span>
                  </div>
                </div>
              )
            })()}
          </div>
        )
      })()}

      {(() => {
        const dLeft = renewalDaysLeft()
        if (dLeft > 14 || dLeft < -1) return null
        const urgent = dLeft <= 3
        const colorClass = urgent ? "warn" : "hint"
        const scheduled = OVERFLOW_DOWNGRADE_SCHEDULED
        return (
          <div className="row row2">
            <div className="card cardInline">
              <span className={"lbl " + (urgent ? "warn" : "")}>
                {scheduled ? "claude2 → pro" : "claude2 renewal"}
              </span>
              <span className="val">
                <span className={colorClass}>{dLeft <= 0 ? "today" : dLeft + "d"}</span>
                <span className="dot">·</span>
                <span className="unit">2026-05-15</span>
                <span className="dot">·</span>
                <span className="hint">
                  {scheduled
                    ? "downgrade scheduled · warm spare, bump to Max if primary caps"
                    : "decide: keep Max 20x or downgrade?"}
                </span>
              </span>
              <div className="tip">
                <span className="tipHead">
                  {scheduled
                    ? "claude2 (overflow) auto-converts to Pro on 2026-05-15"
                    : "claude2 (overflow) auto-renews " + OVERFLOW_RENEWAL_DATE}
                </span>
                <span className="tipKey">days left  </span><span className={"tipVal " + colorClass}>{dLeft}</span>{"\n"}
                <span className="tipKey">now        </span><span className="tipVal">$200/mo (Max 20x)</span>{"\n"}
                {scheduled && [
                  <span key="a" className="tipKey">after      </span>,
                  <span key="b" className="tipVal">$20/mo (Pro) · saves $180/mo</span>,
                  "\n",
                ]}
                {"\n"}
                {scheduled ? [
                  <span key="r1" className="tipVal">decision rationale:</span>, "\n",
                  <span key="r2" className="tipKey">  • prior 3 weeks: 57% / 4% / 3% of Max 20x</span>, "\n",
                  <span key="r3" className="tipKey">  • only 1 cap week out of 3 — overflow is</span>, "\n",
                  <span key="r4" className="tipKey">    a fire extinguisher, not a second engine</span>, "\n",
                  <span key="r5" className="tipKey">  • Pro covers a typical overflow week</span>, "\n",
                  <span key="r6" className="tipKey">    (3–4% of Max 20x ≈ 60–80% of Pro)</span>, "\n",
                  "\n",
                  <span key="r7" className="tipVal warn">if primary caps post-downgrade:</span>, "\n",
                  <span key="r8" className="tipKey">  Settings → Billing → Adjust plan → Max</span>, "\n",
                  <span key="r9" className="tipKey">  Pro CANNOT cover a real cap week —</span>, "\n",
                  <span key="rA" className="tipKey">  exhausts in hours of heavy Opus, not days</span>, "\n",
                ] : [
                  <span key="d1" className="tipVal warn">decide before renewal:</span>, "\n",
                  <span key="d2" className="tipKey">  • </span>,
                  <span key="d3" className="tipVal">keep Max 20x</span>,
                  <span key="d4" className="tipKey"> if cap-weeks are routine</span>, "\n",
                  <span key="d5" className="tipKey">  • </span>,
                  <span key="d6" className="tipVal">downgrade to Pro ($20)</span>,
                  <span key="d7" className="tipKey"> if rarely used — saves $180/mo</span>, "\n",
                ]}
                {"\n"}
                <span className="tipNote">
                  Anthropic does NOT prorate downgrades — Max 20x stays
                  active through {OVERFLOW_RENEWAL_DATE}, then Pro begins
                  on the 15th. claude2 stays usable as overflow either
                  way; the post-15 cap is just much smaller.
                </span>
              </div>
            </div>
          </div>
        )
      })()}

    </div>
  )
}
