"""Tests for handoff.py: every idle/busy/loop branch the widget button gates on.

Run: <FDA python> tests/test_handoff.py   (plain asserts, no pytest needed)

Fixtures are written as COMPACT JSON (no spaces after separators) because
real transcripts are, and scan() pre-filters raw lines on b'"type":"assistant"'.
A spaced fixture would silently skip every line and read as idle.
"""
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import handoff  # noqa: E402
import claude_code_usage as ccu  # noqa: E402

NOW = time.time()
T0 = NOW - 3600


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat().replace("+00:00", "Z")


def A(t, stop, *blocks, **extra):
    return {"type": "assistant", "timestamp": iso(t), **extra,
            "message": {"stop_reason": stop, "content": list(blocks)}}


def U(t, content, **extra):
    return {"type": "user", "timestamp": iso(t), **extra, "message": {"content": content}}


def Q(t, op, content=None):
    d = {"type": "queue-operation", "operation": op, "timestamp": iso(t)}
    if content is not None:
        d["content"] = content
    return d


def text(s):
    return {"type": "text", "text": s}


def use(tid, name, **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def result(tid, body):
    return U(T0 + 20, [{"type": "tool_result", "tool_use_id": tid, "content": body}])


def note(task, status="completed"):
    s = f"<status>{status}</status>" if status else "<event>line</event>"
    return f"<task-notification>\n<task-id>{task}</task-id>\n{s}\n</task-notification>"


def write(lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for d in lines:
        f.write(json.dumps(d, separators=(",", ":")) + "\n")
    f.close()
    return f.name


def verdict(lines, since=None):
    return handoff.evaluate(handoff.scan(write(lines), since), now=NOW)


BG_LAUNCH = [A(T0 + 10, "tool_use", use("t1", "Bash", command="x", run_in_background=True)),
             result("t1", "Command running in background with ID: b1. Output is being written to: /tmp/b1")]
END = A(T0 + 30, "end_turn", text("done"))


def test_fixture_is_compact():
    assert b'"type":"assistant"' in Path(write([END])).read_bytes()


def test_turn_states():
    assert verdict([END])["ready"]
    v = verdict([A(T0, "tool_use", use("t", "Read", file_path="x"))])
    assert not v["ready"] and "waiting on a tool" in v["reason"]
    v = verdict([END, U(T0 + 40, "next task please")])
    assert not v["ready"] and "working" in v["reason"]
    assert verdict([END, U(T0 + 40, "go"), U(T0 + 41, "[Request interrupted by user]")])["ready"]
    local = [U(T0 + 40, "<command-name>/model</command-name>"),
             U(T0 + 41, "<local-command-stdout>Set model</local-command-stdout>"),
             U(T0 + 42, "<local-command-caveat>x</local-command-caveat>", isMeta=True)]
    assert verdict([END] + local)["ready"]
    side = A(T0 + 50, "tool_use", use("s", "Read"), isSidechain=True)
    assert verdict([END, side])["ready"]
    # a cron tick lands as an isMeta user entry: mid-tick the window is busy
    tick = U(T0 + 60, "TICK run x", isMeta=True)
    v = verdict([END, tick])
    assert not v["ready"] and "working" in v["reason"]
    assert verdict([END, tick, A(T0 + 70, "end_turn", text("07:20 | running"))])["ready"]


def test_background_tasks():
    v = verdict(BG_LAUNCH + [END])
    assert not v["ready"] and "1 bg task" in v["reason"]
    assert verdict(BG_LAUNCH + [END, Q(T0 + 60, "enqueue", note("b1")), Q(T0 + 61, "dequeue")])["ready"]
    # completion logged before the launch result must still count
    early = [BG_LAUNCH[0], Q(T0 + 15, "enqueue", note("b1")), Q(T0 + 16, "remove"), BG_LAUNCH[1], END]
    assert verdict(early)["ready"]
    stop = A(T0 + 40, "tool_use", use("t9", "TaskStop", task_id="b1"))
    assert verdict(BG_LAUNCH + [stop, result("t9", "stopped"), END])["ready"]
    # launched before this process started: belonged to a dead process
    assert verdict(BG_LAUNCH + [END], since=T0 + 25)["ready"]


def test_monitor_and_agents():
    mon = [A(T0 + 10, "tool_use", use("m", "Monitor", command="tail -F x")),
           result("m", "Monitor started (task bm1, expires in 30m unless the source ends first")]
    fresh_mon = [A(NOW - 60, "tool_use", use("m", "Monitor", command="x")),
                 U(NOW - 59, [{"type": "tool_result", "tool_use_id": "m",
                               "content": "Monitor started (task bm2, expires in 30m unless"}]),
                 A(NOW - 58, "end_turn", text("ok"))]
    assert not verdict(fresh_mon)["ready"]
    event = [Q(NOW - 30, "enqueue", note("bm2", status=None)), Q(NOW - 29, "dequeue"),
             A(NOW - 20, "end_turn", text("saw event"))]
    assert not verdict(fresh_mon + event)["ready"], "a status-less Monitor event must not end the monitor"
    assert verdict(fresh_mon + event + [Q(NOW - 10, "enqueue", note("bm2", "killed")), Q(NOW - 9, "dequeue"),
                                        A(NOW - 5, "end_turn", text("done"))])["ready"]
    assert verdict(mon + [END])["ready"], "expired an hour ago plus grace"
    agent = [A(T0 + 10, "tool_use", use("g", "Agent", prompt="p")),
             result("g", [{"type": "text", "text": "Async agent launched successfully.\nagentId: a123 (internal)"}])]
    assert not verdict(agent + [END])["ready"]
    assert not verdict(agent + [END, Q(T0 + 90, "enqueue", note("a123"))])["ready"], "about to start a turn"
    assert verdict(agent + [END, Q(T0 + 90, "enqueue", note("a123")), Q(T0 + 91, "dequeue"),
                            A(T0 + 95, "end_turn", text("agent says"))])["ready"]
    sync = [agent[0], result("g", [{"type": "text", "text": "Final report.\nagentId: a456 (for resuming)"}])]
    assert verdict(sync + [END])["ready"]


def test_loops_carry_not_block():
    cron = [A(T0 + 10, "tool_use", use("c", "CronCreate", cron="*/10 * * * *", prompt="TICK run x")),
            result("c", "Scheduled recurring job 24bdb49f (Every 10 minutes). Session-only")]
    v = verdict(cron + [END])
    assert v["ready"] and len(v["loops"]) == 1 and v["loops"][0]["prompt"] == "TICK run x"
    dele = A(T0 + 40, "tool_use", use("d", "CronDelete", id="24bdb49f"))
    assert verdict(cron + [dele, result("d", "Cancelled"), END])["loops"] == []
    old = [A(NOW - 8 * 86400, "tool_use", cron[0]["message"]["content"][0]),
           U(NOW - 8 * 86400 + 1, cron[1]["message"]["content"])]
    assert verdict(old + [END])["loops"] == [], "recurring jobs expire after 7 days"
    once = [A(T0 + 10, "tool_use", use("o", "CronCreate", cron="30 14 18 9 *", prompt="ONCE check", recurring=False)),
            result("o", "Scheduled one-shot job 77aa (Sep 18 14:30). Session-only")]
    assert len(verdict(once + [END])["loops"]) == 1
    assert verdict(once + [END, Q(T0 + 70, "enqueue", "ONCE check"), Q(T0 + 71, "dequeue"),
                           A(T0 + 80, "end_turn", text("checked"))])["loops"] == []
    wake = A(NOW - 100, "tool_use", use("w", "ScheduleWakeup", delaySeconds=1200, prompt="/loop poll"))
    v = verdict([wake, result("w", "Next wakeup scheduled"), A(NOW - 90, "end_turn", text("ok"))])
    assert v["ready"] and v["loops"][0]["type"] == "wakeup"
    stopw = A(NOW - 80, "tool_use", use("w2", "ScheduleWakeup", stop=True))
    assert verdict([wake, stopw, A(NOW - 70, "end_turn", text("ok"))])["loops"] == []
    fired = A(T0 - 7200, "tool_use", use("w3", "ScheduleWakeup", delaySeconds=60, prompt="/loop poll"))
    assert verdict([fired, END])["loops"] == []


def test_queue():
    v = verdict([END, Q(T0 + 40, "enqueue", "hello")])
    assert not v["ready"] and "input queued" in v["reason"]
    assert verdict([END, Q(T0 + 40, "enqueue", "hello"), Q(T0 + 41, "dequeue")])["ready"]
    assert verdict([Q(T0, "enqueue", "old"), END])["ready"], "queued before the last reply was handled"


def test_conversation_and_baton():
    loop = [A(T0, "tool_use", use("c", "CronCreate", cron="*/10 * * * *", prompt="TICK run x")),
            result("c", "Scheduled recurring job j1 (Every 10 minutes).")]
    lines = [U(T0 - 10, "build the thing"), *loop,
             U(T0 + 30, "TICK run x", isMeta=True), A(T0 + 31, "end_turn", text("still running")),
             U(T0 + 40, "real question<system-reminder>secret harness text</system-reminder>"),
             U(T0 + 41, note("b9")), U(T0 + 42, "<local-command-stdout>x</local-command-stdout>"),
             A(T0 + 43, "end_turn", text("x" * 7000))]
    path = write(lines)
    conv = handoff.conversation(path)
    joined = "\n".join(t for _, t in conv)
    assert "TICK run x" not in [t for r, t in conv if r == "Andy"], "ticks are harness text"
    assert ("Claude", "still running") in conv, "replies to ticks carry the status"
    assert "secret harness text" not in joined and "<task-notification>" not in joined
    assert "Scheduled recurring job" not in joined, "tool output must be stripped"
    assert conv[-1][1].endswith("…[truncated]") and len(conv[-1][1]) < 6100
    with tempfile.TemporaryDirectory() as d:
        handoff.HANDOFFS_DIR = Path(d)
        v = handoff.evaluate(handoff.scan(path), now=NOW)
        meta = {"project": "code/rog_gateway", "context_k": 963.2, "session_id": "s1",
                "cwd": "/x", "account": "primary"}
        out = handoff.write_baton(Path(path), meta, v["loops"])
        body = out.read_text()
        assert out.name.endswith("_code-rog-gateway-auto-handoff.md")
        assert "CronCreate cron=`*/10 * * * *` recurring=true" in body and "TICK run x" in body
        assert "build the thing" in body and "real question" in body


def test_annotate_and_one_threshold():
    idle = write([END])
    s = {"context_tokens": 179_999}
    handoff.annotate(s, idle, 123, None)
    assert s["handoff"] == {"over": False, "threshold_k": 180}
    s = {"context_tokens": 180_000}
    handoff.annotate(s, idle, 123, None)
    assert s["handoff"]["ready"] is True
    s = {"context_tokens": 500_000}
    handoff.annotate(s, idle, None, None)
    assert s["handoff"]["ready"] is False, "no pid, nothing to end"
    s = {"context_tokens": 500_000}
    handoff.annotate(s, "/nonexistent.jsonl", 1, None)
    assert s["handoff"]["reason"] == "state unknown", "render path must not raise"
    assert ccu._classify_session(1, 179.9)[1] == "NORMAL"
    assert ccu._classify_session(1, 180.0)[1] == "HANDOFF"


def test_one_launch_at_a_time():
    import fcntl
    notes = []
    handoff._notify = notes.append
    with tempfile.TemporaryDirectory() as d:
        handoff.LOCK_PATH = Path(d) / ".handoff.lock"
        held = open(handoff.LOCK_PATH, "w")
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)  # a launch in flight
        assert handoff.launch(1, "/nope.jsonl") == 1
        assert notes and "already in progress" in notes[-1]
        fcntl.flock(held, fcntl.LOCK_UN)
        notes.clear()
        assert handoff.launch(1, "/nope.jsonl") == 1
        assert "already in progress" not in notes[-1], "lock free: falls through to the real checks"


if __name__ == "__main__":
    scratch = Path(tempfile.mkdtemp())
    handoff.CACHE_PATH = scratch / "cache.json"
    handoff.LOG_PATH = scratch / "handoff.log"  # never write test runs into the real click log
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
