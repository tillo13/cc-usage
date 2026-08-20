// Pure display formatters for the cc-usage widget.
//
// Split out of cc-usage.jsx 2026-08-19 (file was 1938 lines vs a ~1000
// ceiling). These are total functions of their arguments — no closure, no
// state, no DOM — which is exactly why they belong outside the render.

// ───────────────────────────────────────────────────────────────────
//   helpers
// ───────────────────────────────────────────────────────────────────

export const fmtHM = (h) => {
  if (h == null || isNaN(h)) return "—"
  if (h < 0) h = 0
  const hours = Math.floor(h)
  const mins = Math.round((h - hours) * 60)
  if (hours === 0) return `${mins}m`
  return `${hours}h${String(mins).padStart(2, "0")}m`
}
export const fmtHD = (h) => {
  if (h == null || isNaN(h)) return "—"
  if (h < 24) return fmtHM(h)
  const whole = Math.floor(h)
  const days = h / 24
  return `${whole}h/${days.toFixed(1)}d`
}
export const paceClass = (d) => d == null ? "good" : d >= 40 ? "crit" : d >= 10 ? "warn" : "good"
export const paceBgClass = (d) => d == null ? "bgGood" : d >= 40 ? "bgCrit" : d >= 10 ? "bgWarn" : "bgGood"
export const paceWord = (d) => {
  if (d == null) return "ON PACE"
  if (d >= 40) return "CRITICAL"
  if (d >= 20) return "VERY HOT"
  if (d >= 10) return "HOT"
  if (d >= -10) return "ON PACE"
  return "COOL"
}
export const clamp = (v) => Math.max(0, Math.min(100, v))

