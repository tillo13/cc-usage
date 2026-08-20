// Deployment + account constants for the cc-usage widget.
//
// Split out of cc-usage.jsx 2026-08-19 so the main file and the row components
// share ONE definition rather than each carrying a copy — the standby row needs
// the overflow dates, the main file needs the interpreter path for `command`.
//
// PYTHON_BIN must be an interpreter with Full Disk Access: Übersicht runs
// widgets under a sandboxed context that cannot read ~/.claude/projects
// otherwise. (The same constraint bites launchd — verified 2026-08-19 that
// CommandLineTools 3.9 and Homebrew 3.14 both EPERM on ~/Desktop, while
// Homebrew 3.11 holds the grant.)

export const PYTHON_BIN = "$HOME/Desktop/code/kicksaw/venv_kicksaw/bin/python3"
export const REPO_ROOT  = "$HOME/Desktop/code/_local_infrastructure/cc_usage"

// Overflow account winds down to Pro on 2026-05-15; the strip shows the ETA.
export const OVERFLOW_RENEWAL_DATE = "2026-05-14"
export const OVERFLOW_DOWNGRADE_SCHEDULED = true   // → Pro on 2026-05-15

export const renewalDaysLeft = () => {
  const now = new Date()
  const renewal = new Date(OVERFLOW_RENEWAL_DATE + "T07:00:00Z") // approx midnight PT
  return Math.ceil((renewal - now) / (1000 * 60 * 60 * 24))
}
