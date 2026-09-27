"""Subagent transcripts (projects/<proj>/<session>/subagents/agent-*.jsonl) are ingested, flagged
is_sidechain, and carry agent_type from the sibling .meta.json. Until 2026-09-27 the backfill never
globbed them, so subagent turns were uncounted and is_sidechain was 0 on all 306,804 turns.

Run: python3 tests/test_subagent_ingest.py   (plain asserts; temp DB, never the real one)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import claude_usage_backfill as bf  # noqa: E402
import claude_usage_db as dbmod  # noqa: E402


def assistant(msg_id, sidechain):
    return {"type": "assistant", "uuid": msg_id + "-u", "sessionId": "sess1", "cwd": "/tmp/proj",
            "timestamp": "2026-09-26T12:00:00.000Z", "requestId": "req-" + msg_id, "isSidechain": sidechain,
            "message": {"id": msg_id, "model": "claude-opus-5-5", "role": "assistant",
                        "content": [{"type": "text", "text": "hi"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5}}}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp, "projects", "-tmp-proj")
        sub = proj / "sess1" / "subagents"
        sub.mkdir(parents=True)
        (proj / "sess1.jsonl").write_text(json.dumps(assistant("m-main", False), separators=(",", ":")) + "\n")
        (sub / "agent-a1.jsonl").write_text(json.dumps(assistant("m-sub", True), separators=(",", ":")) + "\n")
        (sub / "agent-a1.meta.json").write_text(json.dumps({"agentType": "general-purpose"}))
        bf.ACCOUNT_GLOBS = [("primary", "mac", os.path.join(tmp, "projects/*/*.jsonl")),
                            ("primary", "mac", os.path.join(tmp, "projects/*/*/subagents/*.jsonl"))]
        dbmod.DB_PATH = Path(tmp, "usage.db")
        bf.backfill(verbose=False)
        conn = dbmod.connect()
        rows = dict(conn.execute("SELECT message_id, is_sidechain || '|' || COALESCE(agent_type, '')"
                                 " FROM turns").fetchall())
        conn.close()
    assert rows.get("m-main") == "0|", rows
    assert rows.get("m-sub") == "1|general-purpose", f"subagent turn missing or unflagged: {rows}"
    print("ok: main turn plain, subagent turn ingested with is_sidechain=1 and agent_type")


if __name__ == "__main__":
    main()
