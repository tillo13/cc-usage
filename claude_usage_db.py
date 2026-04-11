"""
SQLite schema + helpers for the Claude Code usage tracker.

Six tables:

    snapshots     — poll results from /api/oauth/usage (Anthropic's
                    authoritative weekly/session quota view, as % utilization
                    + reset timestamps)
    turns         — one row per assistant message, backfilled from
                    ~/.claude/projects/*/*.jsonl (per-turn token counts +
                    session + project + model metadata + content stats)
    tool_calls    — one row per `tool_use` block inside an assistant turn
                    (tool name, input JSON, size). Answers "which tools did I
                    use and how often."
    tool_results  — one row per `tool_result` block inside a user turn
                    (paired with tool_calls via tool_use_id; carries error
                    flag + result payload size)
    user_prompts  — one row per `user` event (either a real prompt or a
                    tool_result wrapper). Lets us count human prompts,
                    prompt length, pasted images, etc.
    events        — catchall for non-turn events: system turn_duration
                    markers, permission-mode flips, file-history snapshots,
                    attachments, queue-operation, last-prompt, etc. Stored
                    with raw payload JSON for ad-hoc queries.

Together these let us correlate "tokens spent" (turns) with "quota %
consumed" (snapshots) AND explain where the tokens *went* (tool_calls +
content stats).

DB path: <cc_usage_repo_root>/data/claude_usage.db  (resolved relative to
this file).

Idempotency: every table uses a stable UUID from the JSONL as its UNIQUE
key, so re-running the backfill is always safe.

Schema evolution: `connect()` applies forward-only migrations via
PRAGMA table_info — safe to call against a stale DB; any missing columns
are added in place with ALTER TABLE ADD COLUMN.
"""

import sqlite3
from pathlib import Path

# Sibling data/ dir — keeps this repo self-contained so the widget stack can
# live under _infrastructure/cc_usage/ with no absolute-path dependencies.
DB_PATH = Path(__file__).resolve().parent / "data" / "claude_usage.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                        TEXT NOT NULL,           -- ISO UTC when fetched
    source                    TEXT NOT NULL,           -- 'cli' | 'launchd' | 'hook' | 'backfill'
    five_hour_pct             REAL,
    five_hour_reset           TEXT,
    seven_day_pct             REAL,
    seven_day_reset           TEXT,
    seven_day_sonnet_pct      REAL,
    seven_day_sonnet_reset    TEXT,
    seven_day_opus_pct        REAL,
    seven_day_opus_reset      TEXT,
    extra_used_cents          INTEGER,
    extra_limit_cents         INTEGER,
    extra_reset               TEXT,
    raw_json                  TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);

CREATE TABLE IF NOT EXISTS turns (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_uuid                    TEXT NOT NULL UNIQUE,  -- JSONL top-level uuid
    message_id                      TEXT,                  -- Anthropic msg_*
    request_id                      TEXT,                  -- API req_*
    session_id                      TEXT NOT NULL,         -- Claude Code session uuid
    parent_uuid                     TEXT,                  -- for conversation tree
    ts                              TEXT NOT NULL,         -- ISO UTC
    project_cwd                     TEXT,                  -- absolute path
    git_branch                      TEXT,
    model                           TEXT,                  -- claude-opus-4-6, sonnet-4-6, haiku-4-5-*
    input_tokens                    INTEGER,
    output_tokens                   INTEGER,
    cache_creation_input_tokens     INTEGER,
    cache_read_input_tokens         INTEGER,
    ephemeral_1h_input_tokens       INTEGER,
    ephemeral_5m_input_tokens       INTEGER,
    service_tier                    TEXT,
    is_sidechain                    INTEGER,               -- 0/1
    cc_version                      TEXT,                  -- Claude Code version string
    source_file                     TEXT                   -- jsonl path (for auditing)
);
CREATE INDEX IF NOT EXISTS idx_turns_ts ON turns(ts);
CREATE INDEX IF NOT EXISTS idx_turns_session_ts ON turns(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_turns_project_ts ON turns(project_cwd, ts);
CREATE INDEX IF NOT EXISTS idx_turns_model_ts ON turns(model, ts);

CREATE TABLE IF NOT EXISTS tool_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_use_id     TEXT NOT NULL UNIQUE,    -- toolu_* from the tool_use block
    message_uuid    TEXT NOT NULL,           -- FK → turns.message_uuid
    session_id      TEXT,
    ts              TEXT NOT NULL,
    project_cwd     TEXT,
    tool_name       TEXT NOT NULL,           -- Bash, Read, Edit, Write, Grep, Glob, Task, Skill, ...
    input_json      TEXT,                    -- raw input payload (trimmed to 4k)
    input_bytes     INTEGER,                 -- full payload size pre-trim
    is_sidechain    INTEGER,
    model           TEXT                     -- carried from parent turn for convenience
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_ts ON tool_calls(ts);
CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_ts ON tool_calls(tool_name, ts);
CREATE INDEX IF NOT EXISTS idx_tool_calls_message ON tool_calls(message_uuid);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session_ts ON tool_calls(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_tool_calls_project_ts ON tool_calls(project_cwd, ts);

CREATE TABLE IF NOT EXISTS tool_results (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_use_id             TEXT NOT NULL UNIQUE,  -- matches tool_calls.tool_use_id
    wrapper_message_uuid    TEXT,                  -- the user msg that held the result
    session_id              TEXT,
    ts                      TEXT,
    is_error                INTEGER,               -- 0/1 from tool_result.is_error
    success                 INTEGER,               -- 0/1 from toolUseResult.success
    result_bytes            INTEGER,               -- size of result content
    command_name            TEXT                   -- from toolUseResult.commandName (slash commands)
);
CREATE INDEX IF NOT EXISTS idx_tool_results_ts ON tool_results(ts);
CREATE INDEX IF NOT EXISTS idx_tool_results_error ON tool_results(is_error, ts);

CREATE TABLE IF NOT EXISTS user_prompts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    message_uuid        TEXT NOT NULL UNIQUE,  -- top-level uuid of the user event
    session_id          TEXT,
    parent_uuid         TEXT,
    prompt_id           TEXT,
    ts                  TEXT NOT NULL,
    project_cwd         TEXT,
    text_chars          INTEGER,               -- sum of user text content length
    image_count         INTEGER,               -- # of image blocks in content
    tool_result_count   INTEGER,               -- # of tool_result blocks (wrappers)
    is_real_prompt      INTEGER,               -- 1 if has text + no tool_result wrappers
    is_sidechain        INTEGER,
    user_type           TEXT,                  -- 'external' (human) / ...
    text_preview        TEXT                   -- first 200 chars of user text (for search)
);
CREATE INDEX IF NOT EXISTS idx_user_prompts_ts ON user_prompts(ts);
CREATE INDEX IF NOT EXISTS idx_user_prompts_session ON user_prompts(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_user_prompts_real ON user_prompts(is_real_prompt, ts);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uuid      TEXT UNIQUE,              -- may be null for events w/o uuid
    type            TEXT NOT NULL,            -- system, permission-mode, attachment, ...
    subtype         TEXT,                     -- e.g. system.turn_duration
    session_id      TEXT,
    parent_uuid     TEXT,
    ts              TEXT,
    project_cwd     TEXT,
    duration_ms     INTEGER,                  -- hoisted from system.turn_duration
    payload_json    TEXT,
    source_file     TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(type, ts);
CREATE INDEX IF NOT EXISTS idx_events_parent ON events(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events(session_id, ts);
"""


# Forward-only column additions for `turns`. Keys are (table, column, type).
# On every connect() we introspect PRAGMA table_info and ADD COLUMN whichever
# of these are missing. SQLite doesn't support `ADD COLUMN IF NOT EXISTS`
# natively, so we introspect ourselves.
_MIGRATIONS = [
    # (table, column_name, sql_type)
    ("turns", "duration_ms",          "INTEGER"),
    ("turns", "stop_reason",          "TEXT"),
    ("turns", "stop_details",         "TEXT"),
    ("turns", "num_thinking_blocks",  "INTEGER"),
    ("turns", "thinking_chars",       "INTEGER"),
    ("turns", "num_text_blocks",      "INTEGER"),
    ("turns", "text_chars",           "INTEGER"),
    ("turns", "num_tool_uses",        "INTEGER"),
    ("turns", "permission_mode",      "TEXT"),
    ("turns", "is_api_error",         "INTEGER"),
    ("turns", "is_compact_summary",   "INTEGER"),
    ("turns", "is_meta",              "INTEGER"),
    ("turns", "iterations_count",     "INTEGER"),
    ("turns", "web_search_requests",  "INTEGER"),
    ("turns", "web_fetch_requests",   "INTEGER"),
    ("turns", "entrypoint",           "TEXT"),
    ("turns", "prompt_id",            "TEXT"),
    ("turns", "user_type",            "TEXT"),
]


def _apply_migrations(conn):
    for table, col, typ in _MIGRATIONS:
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cur.fetchall()}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    conn.commit()


def connect():
    """Open a connection to the usage DB.

    Uses WAL journal mode so readers never block writers (the backfill +
    launchd snapshot + Übersicht widget all touch this DB concurrently).
    The 30s busy_timeout means concurrent writers wait their turn instead
    of erroring out with "database is locked".
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # timeout=30: block up to 30s waiting for a write lock (instead of the
    # default 5s) so the widget never sees a lock error during a backfill.
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    # WAL mode + NORMAL sync = readers never block writers. Persistent once
    # set — these PRAGMAs survive across connections.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(_SCHEMA)
    _apply_migrations(conn)
    return conn


# ------------------------------------------------------------------
# snapshot insert (unchanged)
# ------------------------------------------------------------------

def insert_snapshot(conn, *, ts, source, data):
    """Insert a /api/oauth/usage response. `data` is the raw dict from the API."""
    import json as _json

    def g(bucket, key):
        b = data.get(bucket)
        return (b or {}).get(key)

    extra = data.get("extra_usage") or {}
    conn.execute(
        """
        INSERT INTO snapshots (
            ts, source,
            five_hour_pct, five_hour_reset,
            seven_day_pct, seven_day_reset,
            seven_day_sonnet_pct, seven_day_sonnet_reset,
            seven_day_opus_pct, seven_day_opus_reset,
            extra_used_cents, extra_limit_cents, extra_reset,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts, source,
            g("five_hour", "utilization"),        g("five_hour", "resets_at"),
            g("seven_day", "utilization"),        g("seven_day", "resets_at"),
            g("seven_day_sonnet", "utilization"), g("seven_day_sonnet", "resets_at"),
            g("seven_day_opus", "utilization"),   g("seven_day_opus", "resets_at"),
            extra.get("used_credits"),
            extra.get("monthly_limit"),
            extra.get("resets_at"),
            _json.dumps(data),
        ),
    )
    conn.commit()


# ------------------------------------------------------------------
# row-level upserts — all idempotent via UNIQUE keys
# ------------------------------------------------------------------

def _insert_row(conn, table, row):
    cols = list(row.keys())
    placeholders = ", ".join("?" * len(cols))
    col_list = ", ".join(cols)
    conn.execute(
        f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",
        tuple(row[c] for c in cols),
    )


def upsert_turn(conn, turn):
    """Insert a turn dict. Idempotent via UNIQUE(message_uuid)."""
    _insert_row(conn, "turns", turn)


def upsert_tool_call(conn, row):
    """Insert a tool_call row. Idempotent via UNIQUE(tool_use_id)."""
    _insert_row(conn, "tool_calls", row)


def upsert_tool_result(conn, row):
    """Insert a tool_result row. Idempotent via UNIQUE(tool_use_id)."""
    _insert_row(conn, "tool_results", row)


def upsert_user_prompt(conn, row):
    """Insert a user_prompts row. Idempotent via UNIQUE(message_uuid)."""
    _insert_row(conn, "user_prompts", row)


def upsert_event(conn, row):
    """Insert an events row. Idempotent via UNIQUE(event_uuid) when present."""
    if not row.get("event_uuid"):
        # No stable key → fall through to regular insert. These events (like
        # bare `last-prompt` markers) are rare and harmless if they duplicate.
        cols = list(row.keys())
        placeholders = ", ".join("?" * len(cols))
        col_list = ", ".join(cols)
        conn.execute(
            f"INSERT INTO events ({col_list}) VALUES ({placeholders})",
            tuple(row[c] for c in cols),
        )
        return
    _insert_row(conn, "events", row)


# ------------------------------------------------------------------
# read helpers
# ------------------------------------------------------------------

def query_turns_since(conn, since_iso_utc, until_iso_utc=None):
    """Return all turns in [since, until). until defaults to now."""
    if until_iso_utc:
        return conn.execute(
            "SELECT * FROM turns WHERE ts >= ? AND ts < ? ORDER BY ts",
            (since_iso_utc, until_iso_utc),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM turns WHERE ts >= ? ORDER BY ts",
        (since_iso_utc,),
    ).fetchall()


def query_snapshots_since(conn, since_iso_utc):
    return conn.execute(
        "SELECT * FROM snapshots WHERE ts >= ? ORDER BY ts",
        (since_iso_utc,),
    ).fetchall()


def latest_snapshot(conn):
    row = conn.execute(
        "SELECT * FROM snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    return row


def stats(conn):
    """Quick counts for CLI diagnostics."""
    return {
        "snapshots":    conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],
        "turns":        conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0],
        "tool_calls":   conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0],
        "tool_results": conn.execute("SELECT COUNT(*) FROM tool_results").fetchone()[0],
        "user_prompts": conn.execute("SELECT COUNT(*) FROM user_prompts").fetchone()[0],
        "events":       conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "earliest_turn": conn.execute("SELECT MIN(ts) FROM turns").fetchone()[0],
        "latest_turn":   conn.execute("SELECT MAX(ts) FROM turns").fetchone()[0],
        "sessions":      conn.execute("SELECT COUNT(DISTINCT session_id) FROM turns").fetchone()[0],
        "projects":      conn.execute(
            "SELECT COUNT(DISTINCT project_cwd) FROM turns WHERE project_cwd IS NOT NULL"
        ).fetchone()[0],
    }
