// ROW 3 — standby account strip + mac vitals card, and the overflow notice.
//
// Split out of cc-usage.jsx 2026-08-19: the main file was 1938 lines against a
// ~1000 ceiling and this row was 407 of them.
//
// TWO components, not one wrapped in a fragment. Übersicht 1.6 compiles JSX
// with `{pragma: 'html'}` and NO pragmaFrag configured (see server.js), so
// `<>...</>` would emit a call against an undefined Fragment. esbuild accepts
// fragments happily, so a bundle check alone would not catch it — hence two
// plain components instead. (Function components themselves ARE fine under
// this pragma; verified with a throwaway probe widget 2026-08-19.)
//
// The values these read from the render closure are now props; the JSX bodies
// are otherwise unchanged from what shipped.

import { run } from "uebersicht"
import { clamp, paceClass, paceBgClass } from "./cc-usage.format.jsx"
import { OVERFLOW_RENEWAL_DATE, OVERFLOW_DOWNGRADE_SCHEDULED,
         renewalDaysLeft } from "./cc-usage.config.jsx"

// Whichever account is NOT driving rows 1-2, plus the machine vitals
// card (load / pressure / WindowServer / reapable tabs) and its
// click-to-run cleaner button.
export const StandbyRow = ({ standby, primary, overflow, active, d,
                            standbyIsPrimary }) => {
  if (!standby || !standby.session) return null

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
                    {/* Kernel memory pressure (2026-08-19). Outranks every
                        other signal here: it is the one number that means the
                        machine is genuinely short rather than merely busy.
                        Hidden at normal so the row stays quiet when it is. */}
                    {m.pressure >= 2 && [
                      <span key="pd" className="dot">·</span>,
                      <span key="pu" className="unit">pressure</span>,
                      <span key="pv" className={m.pressure >= 4 ? "crit" : "warn"}>
                        {m.pressure >= 4 ? "critical" : "warn"}
                      </span>,
                    ]}
                    {/* WindowServer + the transparency lever. Called out by
                        name because it is allowlisted — it never appears as an
                        actionable "top offender", yet on a 2-display Retina
                        setup it is routinely the largest single consumer. */}
                    {m.windowserver_pct >= 25 && [
                      <span key="wd" className="dot">·</span>,
                      <span key="wu" className="unit">winsrv</span>,
                      <span key="wv" className={m.windowserver_pct >= 50 ? "warn" : "num"}>
                        {m.windowserver_pct.toFixed(0)}%
                      </span>,
                      m.transparency_off === false && (
                        <span key="wt" className="hint">· transparency on</span>
                      ),
                    ]}
                    {m.chrome_reapable_gb >= 1 && [
                      <span key="gd" className="dot">·</span>,
                      <span key="gu" className="unit">tabs</span>,
                      <span key="gv" className="num">
                        {m.chrome_reapable_gb.toFixed(1)}G
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
                    <span className="tipKey">pressure  </span>
                    <span className={"tipVal " + (m.pressure >= 4 ? "crit" : m.pressure >= 2 ? "warn" : "")}>
                      {m.pressure >= 4 ? "critical" : m.pressure >= 2 ? "warn" : "normal"}
                    </span>
                    <span className="tipKey">  (kernel, not ram%)</span>{"\n"}
                    <span className="tipKey">winserver </span>
                    <span className={"tipVal " + (m.windowserver_pct >= 50 ? "warn" : "")}>
                      {m.windowserver_pct != null ? m.windowserver_pct.toFixed(0) + "%" : "—"}
                    </span>
                    <span className="tipKey">
                      {m.transparency_off ? "  (transparency off)" : "  ← Reduce Transparency is OFF"}
                    </span>{"\n"}
                    <span className="tipKey">idle tabs </span>
                    <span className="tipVal">
                      {m.chrome_reapable_gb != null ? m.chrome_reapable_gb.toFixed(1) + " GB" : "—"}
                    </span>
                    <span className="tipKey">  reapable, tabs reload on click</span>{"\n"}
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
}

// Overflow winds down to Pro — shown only inside the ETA window.
export const OverflowNotice = () => {

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
}
