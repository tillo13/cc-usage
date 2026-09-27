// Local-servers chip for the mac vitals row (2026-09-27).
//
// Python (claude_code_usage._local_servers_snapshot -> deploy/local_cleanup.snapshot) counts the
// dev servers our sessions left running on the Mac: orphaned python/node processes working in
// ~/Desktop/code or a temp dir. Apps run in the cloud, so the count should sit at 0.
//   running > 0 → "local N" (amber once any is stale)
//   stale   > 0 → a "■ stop N" button, same shape as ▶ clean / ▶ handoff. Click runs
//                 local-cleanup: SIGTERM, then SIGKILL after 5 s, only servers up 3h+ so a
//                 server another window started a minute ago is never cut off. Every
//                 `deploy` runs the same script at the end.
import { run } from "uebersicht"

export const LocalChip = ({ l }) => {
  if (!l || !l.running) return null
  const tip = (l.items || []).map(i => (i.stale ? "■ " : "  ") + i.pid + "  up " + i.up + "  " + i.where + "  " + i.cmd).join("\n")
  return [
    <span key="ld" className="dot">·</span>,
    <span key="lu" className="unit">local</span>,
    <span key="lv" className={l.stale ? "warn" : "num"} title={tip}>{l.running}</span>,
    l.stale > 0 && (
      <span
        key="lb"
        className="macBtn warn macBtnDue"
        onClick={() => {
          try { run("PATH=/usr/bin:/bin:/usr/sbin:/sbin $HOME/.local/bin/local-cleanup") } catch (e) { /* keep widget alive */ }
        }}
        title={"Stop " + l.stale + " local server(s) up " + l.min_age_hours + "h+ (the same cleanup every deploy runs):\n" + tip}
      >
        ■ stop {l.stale}
      </span>
    ),
  ]
}
