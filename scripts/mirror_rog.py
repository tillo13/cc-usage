#!/usr/bin/env python3
"""Mirror the ROG (Windows) Claude Code transcripts to a LOCAL dir.

cc-usage ingests ROG windows from this local mirror, NEVER from the SMB mount,
so the always-visible widget can't freeze on a wedged remote mount. If the ROG
is off / unmounted, the mirror just goes stale.

Run by launchd (com.cc-usage.rog-mirror) via the Full-Disk-Access venv python —
launchd-spawned /bin/bash is TCC-blocked from reading scripts under ~/Desktop.
subprocess timeout is the watchdog: a wedged SMB mount can't hang it.
"""
import os
import subprocess
import time
from pathlib import Path

SRC = "/tmp/rog_c/Users/mac/.claude/projects/"
DST = os.path.expanduser("~/.claude-rog/projects/")
LOG = "/tmp/cc_usage_rog_mirror.log"


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


def main():
    os.makedirs(DST, exist_ok=True)
    if not os.path.isdir(SRC):
        log("SMB mount absent — skip, mirror left stale")
        return 0
    try:
        subprocess.run(
            ["/usr/bin/rsync", "-rt",
             "--include=*/", "--include=*.jsonl", "--exclude=*", SRC, DST],
            timeout=90, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        rc = "ok"
    except subprocess.TimeoutExpired:
        rc = "timeout(90s) — SMB likely wedged"
    except Exception as e:
        rc = f"error: {e}"
    n = sum(1 for _ in Path(DST).rglob("*.jsonl"))
    log(f"mirror rsync {rc}, {n} jsonl local")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
