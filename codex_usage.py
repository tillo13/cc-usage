"""Codex usage: incremental local accounting + cached app-server quota.

Collector: python codex_usage.py --collect [--codex-bin /path/to/codex]
Read-only widget/CLI: python codex_usage.py
No model calls, auth-file parsing, or network work on the widget path.
"""
import argparse
import fcntl
import hashlib
import json
import os
import selectors
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / 'data' / 'claude_usage.db'
CACHE_PATH = HERE / 'data' / 'codex_usage.json'
CODEX_HOME = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
TZ = ZoneInfo(os.environ.get('CC_USAGE_TZ', 'America/Los_Angeles'))
TOKEN_KEYS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')


def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS codex_files (
        path TEXT PRIMARY KEY, offset INTEGER, state TEXT);
      CREATE TABLE IF NOT EXISTS codex_responses (
        id TEXT PRIMARY KEY, session TEXT, ts REAL, project TEXT, model TEXT,
        kind TEXT, input INTEGER, cached INTEGER, output INTEGER, reasoning INTEGER);
      CREATE INDEX IF NOT EXISTS codex_response_time ON codex_responses(ts);
      CREATE INDEX IF NOT EXISTS codex_response_session ON codex_responses(session, kind);
      CREATE TABLE IF NOT EXISTS codex_quota (
        ts REAL, bucket TEXT, source TEXT, payload TEXT,
        PRIMARY KEY(ts, bucket, source));
      CREATE TABLE IF NOT EXISTS codex_state (key TEXT PRIMARY KEY, value TEXT);
      CREATE VIEW IF NOT EXISTS codex_counted AS
        SELECT r.* FROM codex_responses r WHERE kind = 'response'
        OR NOT EXISTS (SELECT 1 FROM codex_responses a
                       WHERE a.session = r.session AND a.kind = 'response');
    ''')
    return db


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def quota_insert(db, ts, bucket, source):
    if not isinstance(bucket, dict):
        return
    key = bucket.get('limit_id') or bucket.get('limitId') or 'codex'
    db.execute('INSERT OR IGNORE INTO codex_quota VALUES (?,?,?,?)',
               (ts, key, source, json.dumps(bucket)))


def ingest_file(db, path):
    """Complete lines only. Offsets and inserts commit together; replay is safe."""
    row = db.execute('SELECT offset,state FROM codex_files WHERE path=?', (str(path),)).fetchone()
    offset, state = (row['offset'], json.loads(row['state'])) if row else (0, {})
    if path.stat().st_size < offset:
        offset, state = 0, {}
    if path.stat().st_size == offset:
        return
    with path.open('rb') as stream:
        stream.seek(offset)
        while True:
            line = stream.readline()
            if not line or not line.endswith(b'\n'):
                break
            offset = stream.tell()
            # Avoid decoding huge tool results or images.
            if not any(k in line[:200] for k in (b'"session_meta"', b'"turn_context"',
                                                b'"token_usage_record"', b'"event_msg"')):
                continue
            try:
                item = json.loads(line)
                p = item.get('payload') or {}
                typ = item.get('type')
                if typ == 'session_meta':
                    state['session'] = p.get('id', path.stem)
                    state['project'] = p.get('cwd', 'unknown')
                elif typ == 'turn_context':
                    state['model'] = p.get('model', 'unknown')
                    state['project'] = p.get('cwd', state.get('project', 'unknown'))
                elif typ == 'token_usage_record':
                    usage = p.get('usage')
                    if usage and p.get('response_id'):
                        insert_response(db, p['response_id'], state, item['timestamp'], usage, 'response')
                elif typ == 'event_msg' and p.get('type') == 'token_count':
                    ts = timestamp(item['timestamp'])
                    quota_insert(db, ts, p.get('rate_limits'), 'transcript')
                    info = p.get('info') or {}
                    total = info.get('total_token_usage')
                    if total:
                        previous = state.get('total')
                        # Legacy logs: cumulative deltas, never sums of snapshots.
                        # A decreasing counter (e.g. compaction) establishes a new baseline.
                        if previous is None or all(total.get(k, 0) >= previous.get(k, 0) for k in TOKEN_KEYS):
                            delta = {k: total.get(k, 0) - (previous or {}).get(k, 0) for k in TOKEN_KEYS}
                            digest = hashlib.sha256(json.dumps([state.get('epoch', 0), total], sort_keys=True).encode()).hexdigest()
                            if delta['input_tokens'] or delta['output_tokens']:
                                insert_response(db, 'legacy:' + state.get('session', path.stem) + ':' + digest,
                                                state, item['timestamp'], delta, 'legacy')
                        else:
                            state['epoch'] = state.get('epoch', 0) + 1
                        state['total'] = total
            except (ValueError, TypeError, KeyError):
                continue
    db.execute('INSERT OR REPLACE INTO codex_files VALUES (?,?,?)',
               (str(path), offset, json.dumps(state)))


def insert_response(db, key, state, ts, usage, kind):
    db.execute('INSERT OR IGNORE INTO codex_responses VALUES (?,?,?,?,?,?,?,?,?,?)',
               (key, state.get('session', 'unknown'), timestamp(ts), state.get('project', 'unknown'),
                state.get('model', 'unknown'), kind, *(max(0, int(usage.get(k) or 0)) for k in TOKEN_KEYS)))


def fetch_quota(binary, timeout=25):
    """Bounded, read-only JSON-RPC session. Never starts or resumes a thread."""
    proc = subprocess.Popen([binary, 'app-server', '--listen', 'stdio://'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    pending = b''
    deadline = time.monotonic() + timeout

    def send(obj):
        proc.stdin.write((json.dumps(obj) + '\n').encode())
        proc.stdin.flush()

    def receive(wanted):
        nonlocal pending
        while time.monotonic() < deadline:
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get('id') == wanted:
                    if 'error' in msg:
                        raise RuntimeError('Codex quota request failed: ' + str(msg['error'].get('code')))
                    return msg['result']
            if sel.select(max(0, deadline - time.monotonic())):
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError('Codex app-server exited before returning quota')
                pending += chunk
        raise TimeoutError('Codex quota request timed out')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'cc_usage', 'version': '1.0.0'}}})
        receive(1)
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'account/rateLimits/read', 'params': {}})
        return receive(2)
    finally:
        sel.close()
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        proc.stdin.close()
        proc.stdout.close()


def normalize(bucket):
    windows = []
    for slot in ('primary', 'secondary'):
        raw = bucket.get(slot)
        if not isinstance(raw, dict):
            continue
        used = raw.get('usedPercent', raw.get('used_percent'))
        minutes = raw.get('windowDurationMins', raw.get('window_minutes'))
        reset = raw.get('resetsAt', raw.get('resets_at'))
        if used is None or not minutes or not reset:
            continue
        windows.append({'slot': slot, 'used_pct': float(used), 'minutes': float(minutes),
                        'reset_at': float(reset)})
    return windows


def build_payload(db, now=None):
    now = time.time() if now is None else now
    today = datetime.fromtimestamp(now, TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    start = (today - timedelta(days=6)).timestamp()
    rows = db.execute('SELECT * FROM codex_counted WHERE ts>=? AND ts<=?', (start, now)).fetchall()
    daily = {(today - timedelta(days=i)).date().isoformat(): 0 for i in range(6, -1, -1)}
    projects, models = {}, {}
    today_tokens = today_responses = cached = inputs = 0
    for row in rows:
        tokens = row['input'] + row['output']  # Cached input and reasoning are subsets.
        day = datetime.fromtimestamp(row['ts'], TZ).date().isoformat()
        daily[day] = daily.get(day, 0) + tokens
        projects[row['project']] = projects.get(row['project'], 0) + tokens
        models[row['model']] = models.get(row['model'], 0) + tokens
        if row['ts'] >= today.timestamp():
            today_tokens += tokens
            today_responses += 1
            cached += row['cached']
            inputs += row['input']
    windows = []
    for latest in db.execute('SELECT q.* FROM codex_quota q JOIN '
                             '(SELECT bucket,MAX(ts) ts FROM codex_quota GROUP BY bucket) n '
                             'ON q.bucket=n.bucket AND q.ts=n.ts GROUP BY q.bucket'):
        bucket = json.loads(latest['payload'])
        history = db.execute('SELECT ts,payload FROM codex_quota WHERE bucket=? AND ts>=? AND ts<? ORDER BY ts',
                             (latest['bucket'], latest['ts'] - 86400, latest['ts'] - 900)).fetchall()
        for w in normalize(bucket):
            days_left = max(0, (w['reset_at'] - now) / 86400)
            expired = now >= w['reset_at']
            stale = now - latest['ts'] > 1800 or expired
            w.update(bucket=latest['bucket'], observed_at=latest['ts'], source=latest['source'],
                     stale=stale, expired=expired, days_left=days_left,
                     budget_per_day=max(0, 99 - w['used_pct']) / days_left if days_left else None,
                     projected_pct=None, rate_per_day=None)
            for old in history:
                matching = [x for x in normalize(json.loads(old['payload']))
                            if x['slot'] == w['slot'] and x['reset_at'] == w['reset_at']
                            and x['minutes'] == w['minutes']]
                if not matching or matching[0]['used_pct'] > w['used_pct']:
                    continue
                rate = (w['used_pct'] - matching[0]['used_pct']) / ((latest['ts'] - old['ts']) / 86400)
                w['rate_per_day'] = round(rate, 2)
                if not stale:
                    w['projected_pct'] = round(w['used_pct'] + rate * ((w['reset_at'] - latest['ts']) / 86400), 1)
                break
            windows.append(w)
    return {'collected_at': now, 'subscription_usd': 100, 'windows': windows,
            'today': {'tokens': today_tokens, 'responses': today_responses,
                      'cache_hit_pct': round(cached / inputs * 100, 1) if inputs else None},
            'daily': [{'date': d, 'tokens': n} for d, n in daily.items()],
            'projects': [{'project': p, 'tokens': n} for p, n in sorted(projects.items(), key=lambda x: -x[1])[:8]],
            'models': [{'model': m, 'tokens': n} for m, n in sorted(models.items(), key=lambda x: -x[1])],
            'timezone': str(TZ), 'coverage': 'Local Codex transcripts; last 7 calendar days'}


def cached_payload(path=CACHE_PATH):
    """Cheap and offline; recompute staleness even if the collector has stopped."""
    try:
        payload = json.loads(path.read_text())
        now = time.time()
        payload['collector_stale'] = now - payload['collected_at'] > 180
        for w in payload.get('windows', []):
            w['expired'] = now >= w['reset_at']
            w['stale'] = now - w['observed_at'] > 1800 or w['expired']
            w['days_left'] = max(0, (w['reset_at'] - now) / 86400)
            if w['stale']:
                w['projected_pct'] = None
        return payload
    except (OSError, ValueError, KeyError, TypeError):
        return None


def collect(binary=None, offline=False, home=CODEX_HOME, db_path=DB_PATH, cache_path=CACHE_PATH):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with (cache_path.parent / '.codex_usage.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        db = connect(db_path)
        try:
            # Only local, explicitly scoped transcript roots; never follow remote mounts.
            paths = list((home / 'sessions').glob('*/*/*/*.jsonl'))
            paths += list((home / 'archived_sessions').glob('*.jsonl'))
            for path in paths:
                try:
                    with db:
                        ingest_file(db, path)
                except OSError:
                    continue
            row = db.execute("SELECT value FROM codex_state WHERE key='last_poll'").fetchone()
            if not offline and (not row or time.time() - float(row[0]) >= 900):
                with db:
                    db.execute("INSERT OR REPLACE INTO codex_state VALUES ('last_poll',?)", (str(time.time()),))
                try:
                    binary = binary or shutil.which('codex')
                    if not binary:
                        raise RuntimeError('Codex executable not found')
                    reply = fetch_quota(binary)
                    buckets = reply.get('rateLimitsByLimitId') or {'codex': reply.get('rateLimits')}
                    with db:
                        for key, bucket in buckets.items():
                            if bucket:
                                bucket = dict(bucket, limitId=key)
                                quota_insert(db, time.time(), bucket, 'app-server')
                    print('Codex quota refreshed', flush=True)
                except (OSError, RuntimeError, TimeoutError) as exc:
                    print(str(exc) + '; retaining last observed quota', flush=True)
            payload = build_payload(db)
            tmp = cache_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(payload))
            tmp.replace(cache_path)
            print('Codex collected: %d files, %d responses today, %d quota windows' %
                  (len(paths), payload['today']['responses'], len(payload['windows'])), flush=True)
        finally:
            db.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--collect', action='store_true')
    ap.add_argument('--offline', action='store_true', help='ingest local logs without polling quota')
    ap.add_argument('--codex-bin')
    args = ap.parse_args()
    if args.collect:
        collect(args.codex_bin, args.offline)
    else:
        print(json.dumps(cached_payload() or {}))


if __name__ == '__main__':
    main()
