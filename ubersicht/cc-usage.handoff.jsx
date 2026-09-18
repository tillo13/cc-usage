// Handoff chip for the WINDOWS strip (2026-09-18).
//
// Python (handoff.annotate) tags each live Mac window with
// `handoff = { over, ready, reason, loops }`. Over the one handoff threshold
// (180k, handoff.HANDOFF_CTX_TOKENS):
//   ready  → a pulsing "▶ handoff" button, same shape as the mac cleaner's.
//            Click runs handoff.py launch: re-checks idle, writes a baton to
//            ~/.claude/handoffs/, opens a fresh Terminal window in the same
//            project on the same account, then ends the old claude process
//            (tab + scrollback stay; `claude --resume` brings it back).
//   busy   → the reason as text ("busy: 2 bg tasks"). No button, so a click
//            can never cut off work in flight.
// ROG windows carry no pid (can't launch or end a process there from the
// Mac), so they keep a plain "⚠ handoff" flag.
import { run } from "uebersicht"
import { PYTHON_BIN, REPO_ROOT } from "./cc-usage.config.jsx"

export const HandoffChip = ({ s }) => {
  const cls = s.band === "crit" ? "crit" : "warn"
  const h = s.handoff
  if (!h) {
    return s.host === "rog" && (s.band === "warn" || s.band === "crit")
      ? <span className={"winFlag " + cls}>⚠ handoff</span>
      : null
  }
  if (!h.over) return null
  if (!h.ready) {
    return (
      <span className="winFlag warn" title={"Over " + h.threshold_k + "k, but not safe to hand off yet. The button appears once this window is idle."}>
        {h.reason}
      </span>
    )
  }
  const cmd = "PATH=/usr/bin:/bin:/usr/sbin:/sbin " +
    `${PYTHON_BIN} ${REPO_ROOT}/handoff.py launch --pid ${s.pid} --transcript '${s.transcript}'`
  return (
    <span
      className={"macBtn macBtnDue " + cls}
      onClick={() => {
        try { run(cmd) } catch (e) { /* keep widget alive */ }
      }}
      title={"Idle and over " + h.threshold_k + "k. Click: fresh window in this project reads the conversation tail, then this claude process ends (tab and scrollback stay; claude --resume brings it back)."
        + (h.loops ? " Carries " + h.loops + " loop(s) to the new window." : "")}
    >
      ▶ handoff{h.loops ? " +" + h.loops + " loop" + (h.loops > 1 ? "s" : "") : ""}
    </span>
  )
}
