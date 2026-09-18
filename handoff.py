"""One-click handoff for fat Claude Code windows.

Render path (widget, every 60s): `annotate()` tags each live Mac window with
`handoff = {over, ready, reason, loops}`. The button only shows when the window
is over HANDOFF_CTX_TOKENS AND idle, so a click never cuts off work in flight.

Click path: `handoff.py launch --pid PID --transcript PATH`
  1. re-checks idle against the transcript (state may have moved since render)
  2. writes a baton to ~/.claude/handoffs/: the opening request + conversation
     tail with tool output stripped, plus any loops to re-arm
  3. opens a new Terminal window in the same project (titled with it) on the
     same account, laid over the old window with its profile, started with a
     one-line prompt that points at the baton, which carries the instructions
  4. once the new claude process is up, ends the old one by PID. The tab and
     its scrollback stay; `claude --resume` brings the old session back.

Loops (CronCreate / ScheduleWakeup) live only inside their session, so they
are carried in the baton and re-armed by the new session rather than blocking.
"""
import argparse
import fcntl
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# The one handoff threshold: the context-compaction skill's 180k, the LIVE
# card's HANDOFF band (claude_code_usage._classify_session) and the button.
HANDOFF_CTX_TOKENS = 180_000

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE / "data" / ".handoff_scan_cache.json"
LOG_PATH = HERE / "data" / "handoff.log"
LOCK_PATH = HERE / "data" / ".handoff.lock"
HANDOFFS_DIR = Path.home() / ".claude" / "handoffs"
PROJECTS_DIR = Path.home() / ".claude" / "projects"

TAIL_CHARS = 60_000      # ~15k tokens of recent conversation
MSG_CHARS = 6_000        # one pasted log shouldn't eat the whole tail
FIRST_CHARS = 4_000
MONITOR_GRACE_SEC = 300
CRON_TTL_SEC = 7 * 86400          # recurring CronCreate jobs auto-expire
WAKE_JITTER_SEC = 15 * 60         # ScheduleWakeup can fire up to 15 min late
OSASCRIPT = "/usr/bin/osascript"

_RE_BG_BASH = re.compile(r"running in background with ID: (\w+)")
_RE_AGENT = re.compile(r"agentId: (\w+)")
_RE_MONITOR = re.compile(r"Monitor started \(task (\w+)(?:, expires in (\d+)\s*([smh]))?")
_RE_CRON_JOB = re.compile(r"Scheduled .*?job (\w+)")
_RE_TASK_ID = re.compile(r"<task-id>(\w+)</task-id>")
_RE_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_WATCHED_TOOLS = {"Bash", "Agent", "Task", "Monitor", "TaskStop",
                  "CronCreate", "CronDelete", "ScheduleWakeup"}


def _epoch(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _result_text(block):
    c = block.get("content")
    return c if isinstance(c, str) else json.dumps(c)


def _finish_tasks(text, bg, done):
    """Drop tasks whose final notification is in `text`. Only a notification
    with a <status> is final: Monitor sends status-less ones per event.
    The queue-operation log is the reliable copy; the same notification may
    also land as a user message or be absorbed mid-turn as an attachment."""
    for chunk in text.split("<task-notification>")[1:]:
        m = _RE_TASK_ID.search(chunk)
        if m and "<status>" in chunk.split("</task-notification>")[0]:
            bg.pop(m.group(1), None)
            done.add(m.group(1))  # a fast task can finish before its launch result is logged


def _is_local_command(text):
    t = text.lstrip()
    return t.startswith(("<local-command", "<command-name>"))


def scan(path, since=None):
    """Read a session transcript into the facts `evaluate` needs.

    `since` (epoch) is the live process's start: background tasks, loops and
    queue entries from before it belonged to an earlier process and are dead.
    """
    last = "idle"            # idle | tool (awaiting a tool / permission) | turn
    last_asst_ts = 0.0
    watched = {}             # tool_use_id -> (name, input, ts)
    bg, crons, done = {}, {}, set()
    wake = None
    enq = deq = 0
    last_enq_ts = 0.0
    enq_contents = []
    with open(path, "rb") as fh:
        for raw in fh:
            if not (b'"type":"assistant"' in raw or b'"type":"user"' in raw
                    or b'"type":"queue-operation"' in raw):
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("isSidechain"):
                continue
            ts = _epoch(d.get("timestamp")) or 0.0
            fresh = since is None or ts >= since - 5
            kind = d.get("type")
            if kind == "queue-operation":
                if not fresh:
                    continue
                op = d.get("operation")
                if op == "enqueue":
                    enq += 1
                    last_enq_ts = ts
                    body = d.get("content") or ""
                    enq_contents.append((ts, body))
                    _finish_tasks(body, bg, done)
                elif op in ("dequeue", "remove"):
                    deq += 1
                continue
            msg = d.get("message") or {}
            content = msg.get("content")
            if kind == "assistant":
                last = "tool" if msg.get("stop_reason") == "tool_use" else "idle"
                last_asst_ts = ts
                for b in content or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in _WATCHED_TOOLS and fresh:
                        inp = b.get("input") or {}
                        name = b["name"]
                        if name == "TaskStop":
                            tid = inp.get("task_id") or inp.get("shell_id")
                            bg.pop(tid, None)
                            done.add(tid)
                        elif name == "CronDelete":
                            crons.pop(inp.get("id"), None)
                        elif name == "ScheduleWakeup":
                            wake = None if inp.get("stop") else {
                                "prompt": inp.get("prompt") or "",
                                "fire": ts + float(inp.get("delaySeconds") or 0)}
                        elif name != "Bash" or inp.get("run_in_background"):
                            watched[b["id"]] = (name, inp, ts)
                continue
            # user entry. isMeta entries still count: cron / wakeup ticks, skill
            # bodies and images all arrive as isMeta and start or belong to a
            # turn. The one that doesn't, <local-command-caveat>, is filtered
            # by _is_local_command below.
            if d.get("isCompactSummary"):
                continue
            if isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                last = "turn"
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                        continue
                    w = watched.pop(b.get("tool_use_id"), None)
                    if not w:
                        continue
                    name, inp, t0 = w
                    text = _result_text(b)
                    if name == "CronCreate":
                        m = _RE_CRON_JOB.search(text)
                        if m:
                            crons[m.group(1)] = {
                                "cron": inp.get("cron"), "prompt": inp.get("prompt") or "",
                                "recurring": inp.get("recurring", True), "ts": t0}
                        continue
                    m = (_RE_BG_BASH.search(text) if name == "Bash"
                         else _RE_MONITOR.search(text) if name == "Monitor"
                         else _RE_AGENT.search(text) if "Async agent launched" in text
                         else None)
                    if not m:
                        continue  # a synchronous agent (already done), or a failed launch
                    expires = None
                    if name == "Monitor" and m.group(2):
                        expires = t0 + int(m.group(2)) * {"s": 1, "m": 60, "h": 3600}[m.group(3)]
                    if m.group(1) not in done:
                        bg[m.group(1)] = {"kind": name, "ts": t0, "expires": expires}
                continue
            text = _text_of(content).lstrip()
            if "<task-notification>" in text:
                last = "turn"
                _finish_tasks(text, bg, done)
            elif text.startswith("[Request interrupted"):
                last = "idle"
            elif text and not _is_local_command(text):
                last = "turn"
    # A one-shot cron is gone once its prompt has been enqueued.
    for jid, c in list(crons.items()):
        if not c["recurring"] and any(t >= c["ts"] and body.startswith(c["prompt"][:60])
                                      for t, body in enq_contents):
            crons.pop(jid)
    return {"last": last, "bg": bg, "crons": crons, "wake": wake,
            "queued": max(0, enq - deq) if last_enq_ts > last_asst_ts else 0}


def evaluate(facts, now=None):
    """Turn scan facts into {ready, reason, loops}. Time-dependent, so cheap
    to re-run on cached facts every render."""
    now = now or time.time()
    busy = []
    if facts["last"] == "turn":
        busy.append("working")
    elif facts["last"] == "tool":
        busy.append("waiting on a tool")
    live_bg = [b for b in facts["bg"].values()
               if not (b.get("expires") and now > b["expires"] + MONITOR_GRACE_SEC)]
    if live_bg:
        busy.append(f"{len(live_bg)} bg task" + ("s" if len(live_bg) > 1 else ""))
    if facts["queued"]:
        busy.append("input queued")
    loops = [dict(c, type="cron") for c in facts["crons"].values()
             if not c["recurring"] or now - c["ts"] < CRON_TTL_SEC]
    w = facts["wake"]
    if w and w["fire"] + WAKE_JITTER_SEC > now:
        loops.append({"type": "wakeup", "prompt": w["prompt"],
                      "in_sec": max(60, int(w["fire"] - now))})
    return {"ready": not busy, "reason": ("busy: " + ", ".join(busy)) if busy else "idle",
            "loops": loops}


def _cached_scan(path, since):
    try:
        st = path.stat()
    except OSError:
        return None
    key = str(path)
    stamp = [st.st_size, st.st_mtime, since]
    try:
        cache = json.loads(CACHE_PATH.read_text())
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(key)
    if hit and hit.get("stamp") == stamp:
        return hit["facts"]
    facts = scan(path, since)
    cutoff = time.time() - 86400
    cache = {k: v for k, v in cache.items() if v.get("seen", 0) > cutoff}
    cache[key] = {"stamp": stamp, "facts": facts, "seen": time.time()}
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache))
    except OSError:
        pass
    return facts


def annotate(stats, path, pid, proc_start):
    """Attach stats['handoff'] for a live Mac window. Never raises: the widget
    render path must not error (see CLAUDE.md "Widget failure policy")."""
    over = (stats.get("context_tokens") or 0) >= HANDOFF_CTX_TOKENS
    h = {"over": over, "threshold_k": HANDOFF_CTX_TOKENS // 1000}
    if over:
        try:
            v = evaluate(_cached_scan(Path(path), proc_start))
            h.update(ready=v["ready"] and bool(pid), reason=v["reason"],
                     loops=len(v["loops"]))
        except Exception:
            h.update(ready=False, reason="state unknown", loops=0)
    stats["handoff"] = h


# ---------- click path ----------

def conversation(path):
    """[(role, text)] of what was said, tool I/O and harness chatter stripped.
    isMeta entries (loop ticks, skill bodies, image stubs) are harness text,
    not Andy's words, so they're dropped; Claude's replies to ticks stay."""
    out = []
    with open(path, "rb") as fh:
        for raw in fh:
            if b'"type":"assistant"' not in raw and b'"type":"user"' not in raw:
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("isSidechain") or d.get("isMeta") or d.get("isCompactSummary"):
                continue
            content = (d.get("message") or {}).get("content")
            if d.get("type") == "assistant":
                text = _text_of(content).strip()
                if text:
                    out.append(("Claude", text))
                continue
            text = _RE_REMINDER.sub("", _text_of(content)).strip()
            if not text or _is_local_command(text) or text.startswith(("<task-notification>", "[Request interrupted")):
                continue
            out.append(("Andy", text))
    return [(r, t if len(t) <= MSG_CHARS else t[:MSG_CHARS] + " …[truncated]") for r, t in out]


def write_baton(path, meta, loops, now=None):
    msgs = conversation(path)
    tail, used = [], 0
    for r, t in reversed(msgs):
        if used + len(t) > TAIL_CHARS and tail:
            break
        tail.append((r, t))
        used += len(t)
    tail.reverse()
    first = next((t for r, t in msgs if r == "Andy"), "")
    rearm = " Re-create the loops under 'Loops to re-arm' exactly as written." if loops else ""
    lines = [
        f"# Auto handoff: {meta['project']} ({meta['context_k']:.0f}k context)",
        "",
        f"You are picking up from a {meta['context_k']:.0f}k-context session in `{meta['cwd']}`, "
        f"which has been ended. This file holds the opening request and the conversation tail "
        f"with tool output stripped; the full transcript is linked below.{rearm} Then give a "
        f"3-line status (what we were doing, where it stands, the next step) and wait.",
        "",
        f"- from session: `{meta['session_id']}`",
        f"- full transcript: `{path}` (grep it for specifics, never read it whole)",
        f"- project dir: `{meta['cwd']}`",
        f"- account: {meta['account']}",
        f"- handed off: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        "## Loops to re-arm",
    ]
    if not loops:
        lines.append("none")
    for lp in loops:
        if lp["type"] == "cron":
            lines.append(f"- CronCreate cron=`{lp['cron']}` recurring={str(lp['recurring']).lower()} prompt:")
        else:
            lines.append(f"- ScheduleWakeup delaySeconds={lp['in_sec']} prompt:")
        lines += ["", "```", lp["prompt"], "```", ""]
    if first and (not tail or first != tail[0][1]):
        lines += ["", "## Opening request", "", first[:FIRST_CHARS]]
    lines += ["", f"## Conversation tail (last {len(tail)} of {len(msgs)} messages, tool output stripped)", ""]
    for r, t in tail:
        lines += [f"**{r}:** {t}", ""]
    HANDOFFS_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", meta["project"].lower()).strip("-") or "session"
    stamp = datetime.now()
    out = HANDOFFS_DIR / f"{stamp:%Y-%m-%d_%H%M}_{slug}-auto-handoff.md"
    if out.exists():
        out = out.with_name(f"{stamp:%Y-%m-%d_%H%M%S}_{slug}-auto-handoff.md")
    out.write_text("\n".join(lines))
    return out


def _log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _notify(msg):
    subprocess.run([OSASCRIPT, "-e", f'display notification "{_as_str(msg)}" with title "cc-usage handoff"'],
                   capture_output=True)


def _as_str(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _proc(pid):
    """(comm, stat, start_epoch) for a pid, or None if it's gone."""
    import claude_code_usage as ccu
    out = subprocess.run(["ps", "-o", "comm=,stat=,lstart=", "-p", str(pid)],
                         capture_output=True, text=True).stdout.strip()
    parts = out.split(None, 2)
    if len(parts) < 3:
        return None
    return parts[0], parts[1], ccu._parse_lstart(parts[2])


def _refuse(msg):
    _log("REFUSED " + msg)
    _notify("Handoff skipped: " + msg)
    return 1


def launch(pid, transcript):
    # One handoff at a time. A double click (or a doubled Übersicht onClick)
    # otherwise runs two launches that both pass the idle check, because the
    # old process only ends once the new one is up: 2026-09-18 10:59 opened
    # two windows for one click. flock releases itself when this process exits.
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return _refuse("a handoff is already in progress")
    import claude_code_usage as ccu
    path = Path(transcript).resolve()
    if path.suffix != ".jsonl" or PROJECTS_DIR.resolve() not in path.parents:
        return _refuse(f"not a session transcript: {transcript}")
    proc = _proc(pid)
    if not proc or proc[0] != "claude" or "+" not in proc[1]:
        return _refuse(f"pid {pid} is not a live claude window")
    cwd = ccu._lsof_cwd_for_pid(str(pid))
    if not cwd or cwd.replace("/", "-").replace("_", "-") != path.parent.name:
        return _refuse(f"pid {pid} isn't driving {path.name}")
    facts = scan(path, proc[2])
    v = evaluate(facts)
    if not v["ready"]:
        return _refuse(f"{Path(cwd).name} is {v['reason']}")
    stats = ccu._scan_session_file(path) or {}
    account = ccu._claude_accounts_for_pids([str(pid)]).get(str(pid), "primary")
    meta = {"project": stats.get("project") or cwd, "context_k": stats.get("context_k") or 0,
            "session_id": stats.get("session_id") or path.stem, "cwd": cwd, "account": account}
    baton = write_baton(path, meta, v["loops"])
    # Short on purpose: Terminal prints claude's arguments in the window title.
    prompt = f"Handoff: read {baton} and follow its instructions."
    alias = "claude2" if account == "overflow" else "claude"
    ended = Path(tempfile.gettempdir()) / f"cc_handoff_{os.getpid()}.ended"
    cmd = _launch_cmd(cwd, alias, prompt, ended)
    old_tty = subprocess.run(["ps", "-o", "tty=", "-p", str(pid)],
                             capture_output=True, text=True).stdout.strip()
    r = subprocess.run([OSASCRIPT, "-e", _open_like_script(cmd, "/dev/" + old_tty)],
                       capture_output=True, text=True)
    tty = r.stdout.strip()
    if r.returncode != 0 or not tty.startswith("/dev/"):
        return _refuse(f"Terminal launch failed ({r.stderr.strip()[:120]}); old window left running")
    new_pid = _wait_for_claude(tty, ended)
    if not new_pid:
        return _refuse(f"new window's claude didn't start; old window left running. Baton: {baton}")
    again = _proc(pid)
    if again and again[2] == proc[2]:  # same process, not a recycled pid
        os.kill(pid, signal.SIGTERM)
    _log(f"OK {meta['project']} {meta['context_k']:.0f}k pid {pid} -> pid {new_pid} on {tty}; "
         f"loops {len(v['loops'])}; baton {baton}")
    return 0


def _launch_cmd(cwd, alias, prompt, ended):
    # ~/.zprofile opens every Terminal window in ~/Desktop/code, and Terminal
    # only learns the cwd from update_terminal_cwd (/etc/zshrc_Apple_Terminal)
    # at a prompt, so without the explicit call every title says "code". The
    # braces keep claude gated on the cd: the claude alias contains a `;`,
    # which would otherwise leave the `&&` guarding only its first half.
    return (f"cd {shlex.quote(cwd)} && {{ update_terminal_cwd 2>/dev/null; "
            f"{alias} {shlex.quote(prompt)}; }}; touch {shlex.quote(str(ended))}")


def _open_like_script(cmd, old_tty):
    """AppleScript: run `cmd` in a new Terminal window laid over the old one,
    same bounds and same profile (current settings), so with 4-5 windows up
    the replacement is obvious. Returns the new tab's tty. Windows are held by
    id, not index: opening a window reorders `windows`. Copying the look is
    best-effort; a failure there never blocks the launch."""
    return f'''tell application "Terminal"
    activate
    set oldWid to missing value
    repeat with w in windows
        repeat with t in tabs of w
            if tty of t is "{old_tty}" then
                set oldWid to id of w
                set oldBounds to bounds of w
                set oldLook to current settings of t
            end if
        end repeat
    end repeat
    set newTab to do script "{_as_str(cmd)}"
    set newTty to tty of newTab
    if oldWid is not missing value then
        try
            set current settings of newTab to oldLook
            repeat with w in windows
                repeat with t in tabs of w
                    if tty of t is newTty then set bounds of w to oldBounds
                end repeat
            end repeat
        end try
    end if
    return newTty
end tell'''


def _wait_for_claude(tty, ended):
    """Pid of the claude that comes up on the new window's tty, or None.

    Bounded on state, not a clock: a claude appears on the tty (success), the
    launch command gets past claude without one (the `touch` marker exists),
    or the window is closed (the tty has no processes). A slow start only logs.
    """
    t0, note_at = time.time(), 30
    while True:
        out = subprocess.run(["ps", "-t", tty.replace("/dev/", ""), "-o", "pid=,stat=,comm="],
                             capture_output=True, text=True).stdout
        rows = [ln.split(None, 2) for ln in out.splitlines() if len(ln.split(None, 2)) == 3]
        for p, stat, comm in rows:
            if comm == "claude" and "+" in stat:
                return int(p)
        if ended.exists():
            _log(f"new window on {tty}: command exited before claude started")
            return None
        if not rows:
            _log(f"new window on {tty} was closed before claude started")
            return None
        if time.time() - t0 >= note_at:
            _log(f"[watchdog] still waiting for claude on {tty} at {note_at}s, not a failure")
            note_at += 30
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("launch", help="hand off an idle window to a fresh one")
    lp.add_argument("--pid", type=int, required=True)
    lp.add_argument("--transcript", required=True)
    sp = sub.add_parser("state", help="print the handoff verdict for a transcript")
    sp.add_argument("transcript")
    a = ap.parse_args()
    if a.cmd == "launch":
        return launch(a.pid, a.transcript)
    print(json.dumps(evaluate(scan(Path(a.transcript))), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
