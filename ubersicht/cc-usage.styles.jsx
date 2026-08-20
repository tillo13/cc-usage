// Presentation layer for the cc-usage widget — the full stylesheet.
//
// Split out of cc-usage.jsx 2026-08-19: that file had reached 1938 lines,
// nearly double the ~1000-line ceiling everything else here is held to.
// This block is 527 lines of pure static CSS with no interpolation and no
// closure dependencies, so it is the cleanest seam in the file — moving it
// costs nothing and takes the main file down by a quarter.
//
// Übersicht 1.6 bundles widgets with browserify + babelify, so imports
// resolve normally. Verified 2026-08-19 that they also resolve through the
// widgets-dir SYMLINK against the repo target, which is why this sibling
// lives here in the repo rather than in ~/Library/.../widgets/.

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
  .bgNote { background: #8E8E93; }
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
    color: #B8C8E0;              /* primary account (~/.claude) — calm blue */
    font-weight: 600;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* overflow account (~/.claude-alt, the Pro spare) — red, so the one alt
     window in a strip of primary ones is instantly distinguishable. Red is
     otherwise unused in this widget (warnings are amber/white), so it carries
     no danger connotation here — it means "this window is on the OTHER account". */
  .winName.winAlt { color: #FF6B5C; }
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
