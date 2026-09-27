// Local-servers count for the mac vitals row (2026-09-27).
//
// Python (claude_code_usage._local_servers_snapshot -> deploy/local_cleanup.snapshot) counts the
// dev servers and scripts our sessions left running on the Mac: orphaned python/node processes
// working in ~/Desktop/code or a temp dir. Apps run in the cloud, so it should sit at 0.
//   running > 0 → "local N", amber once any has been up 3h+.
// No button of its own: ▶ clean (smart_mac_cleaner) stops them along with the listening dev
// servers, and every `deploy` stops the ones up 3h+ (the same local_cleanup code).
export const LocalChip = ({ l }) => {
  if (!l || !l.running) return null
  const tip = "Left running by our sessions; ▶ clean stops them.\n"
    + (l.items || []).map(i => (i.stale ? "■ " : "  ") + i.pid + "  up " + i.up + "  " + i.where + "  " + i.cmd).join("\n")
  return [
    <span key="ld" className="dot">·</span>,
    <span key="lu" className="unit">local</span>,
    <span key="lv" className={l.stale ? "warn" : "num"} title={tip}>{l.running}</span>,
  ]
}
