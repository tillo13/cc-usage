#!/usr/bin/env python3
"""Mirror the ROG (Windows) Claude Code transcripts to a LOCAL dir.

cc-usage ingests ROG windows from this local mirror, NEVER from the SMB mount,
so the always-visible widget can't freeze on a wedged remote mount. If the ROG
is off / unmounted / the laptop is on a different network, the mirror just goes
stale — the widget keeps working off the last copy.

NETWORK-AWARE SELF-HEAL: if the SMB mount has fallen off, we probe whether the
ROG is reachable on the *current* network:
  - reachable (same LAN) → remount and sync. So when the laptop comes back onto
    the ROG's network, the next 15-min run reconnects automatically.
  - unreachable (laptop away / different network) → skip silently, no hang.
Mount creds come from the canonical rog_gateway/.env (single source of truth).
The remount mirrors connect.sh's check_smb logic, reimplemented in Python because
launchd-spawned /bin/bash is TCC-blocked from reading scripts under ~/Desktop —
this runs via the Full-Disk-Access venv python. mount_smbfs is a /sbin system
binary (no TCC issue); subprocess timeouts are the watchdog against a wedged mount.
"""
import os
import socket
import subprocess
import time
from pathlib import Path

SRC = "/tmp/rog_c/Users/mac/.claude/projects/"
DST = os.path.expanduser("~/.claude-rog/projects/")
LOG = "/tmp/cc_usage_rog_mirror.log"
ENV = os.path.expanduser("~/Desktop/code/rog_gateway/.env")


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


def _env():
    """Read ROG creds from the canonical rog_gateway/.env."""
    cfg = {}
    try:
        for line in open(ENV):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return cfg


def _reachable(ip, port=445, timeout=3):
    """Is the ROG's SMB port open on the current network?"""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ensure_mount():
    """Return True if SRC is readable — remounting if the ROG is reachable."""
    if os.path.isdir(SRC):
        return True
    cfg = _env()
    ip = cfg.get("ROG_IP")
    if not ip:
        log("mount down + no ROG_IP in .env — skip")
        return False
    if not _reachable(ip):
        log(f"mount down + ROG {ip} not on this network — skip (laptop away?)")
        return False
    # Reachable but unmounted → remount (same LAN, came back / dropped).
    user = cfg.get("ROG_USER", "mac")
    pw = cfg.get("ROG_PASS", "")
    share = cfg.get("ROG_SHARE", "C_Drive")
    mp = cfg.get("ROG_MOUNT", "/tmp/rog_c")
    real = os.path.realpath(mp)
    os.makedirs(mp, exist_ok=True)
    # Clear any ghost/stale mount the kernel is still holding.
    subprocess.run(["umount", real], timeout=20, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        subprocess.run(["/sbin/mount_smbfs", f"//{user}:{pw}@{ip}/{share}", mp],
                       timeout=30, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        log("mount_smbfs timed out — skip")
        return False
    ok = os.path.isdir(SRC)
    log(f"ROG reachable, remounted {share} → {'OK' if ok else 'FAILED'}")
    return ok


def main():
    os.makedirs(DST, exist_ok=True)
    if not _ensure_mount():
        return 0  # away / mount failed — leave mirror stale, never hang
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
