"""SQLite storage for sessions, messages, attachments and long-term memory."""
import json
import sqlite3
import threading
import time
import uuid

from .config import DATA_DIR

_lock = threading.RLock()
_conn = sqlite3.connect(DATA_DIR / "bridge.db", check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.executescript(
    """
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS sessions(
        id TEXT PRIMARY KEY, title TEXT, model TEXT, created REAL, updated REAL);
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT,
        reasoning TEXT, attachments TEXT, tool_calls TEXT, tool_call_id TEXT, name TEXT, created REAL);
    CREATE INDEX IF NOT EXISTS ix_msg_session ON messages(session_id, id);
    CREATE TABLE IF NOT EXISTS attachments(
        id TEXT PRIMARY KEY, filename TEXT, mime TEXT, kind TEXT, path TEXT, text TEXT, size INTEGER, created REAL);
    CREATE TABLE IF NOT EXISTS memories(
        id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, created REAL);
    """
)
# Separate table (not a new column) so an older server version sharing this database keeps working
_conn.execute("CREATE TABLE IF NOT EXISTS session_stats(session_id TEXT PRIMARY KEY, stats TEXT)")
# Compressed history: messages with id <= upto_id are replaced by `summary` when talking to the model
_conn.execute("CREATE TABLE IF NOT EXISTS session_summary("
              "session_id TEXT PRIMARY KEY, summary TEXT, upto_id INTEGER, created REAL)")
_conn.commit()


def _q(sql, args=(), one=False):
    with _lock:
        cur = _conn.execute(sql, args)
        _conn.commit()
        rows = [dict(r) for r in cur.fetchall()]
    return (rows[0] if rows else None) if one else rows


def _ins(sql, args):
    with _lock:
        cur = _conn.execute(sql, args)
        _conn.commit()
        return cur.lastrowid


# ---- sessions ----
def create_session(title="New chat", model=""):
    sid = uuid.uuid4().hex
    now = time.time()
    _ins("INSERT INTO sessions VALUES(?,?,?,?,?)", (sid, title, model, now, now))
    return get_session(sid)


def get_session(sid):
    return _q("SELECT * FROM sessions WHERE id=?", (sid,), one=True)


def list_sessions():
    return _q("SELECT * FROM sessions ORDER BY updated DESC")


def update_session(sid, **fields):
    fields["updated"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    _q(f"UPDATE sessions SET {cols} WHERE id=?", (*fields.values(), sid))
    return get_session(sid)


def delete_session(sid):
    _q("DELETE FROM session_summary WHERE session_id=?", (sid,))
    _q("DELETE FROM session_stats WHERE session_id=?", (sid,))
    _q("DELETE FROM messages WHERE session_id=?", (sid,))
    _q("DELETE FROM sessions WHERE id=?", (sid,))


def set_stats(sid, stats: dict):
    """Last token / speed / context numbers of a session."""
    _q("INSERT OR REPLACE INTO session_stats VALUES(?,?)", (sid, json.dumps(stats)))


def get_stats(sid):
    r = _q("SELECT stats FROM session_stats WHERE session_id=?", (sid,), one=True)
    return json.loads(r["stats"]) if r else None


def set_summary(sid, summary: str, upto_id: int):
    _q("INSERT OR REPLACE INTO session_summary VALUES(?,?,?,?)", (sid, summary, upto_id, time.time()))


def get_summary(sid):
    return _q("SELECT summary, upto_id FROM session_summary WHERE session_id=?", (sid,), one=True)


def truncate_session(sid, from_message_id):
    """Delete a message and everything after it (used when the user edits a message)."""
    _q("DELETE FROM messages WHERE session_id=? AND id>=?", (sid, from_message_id))
    # an edit inside the summarized part invalidates the summary
    _q("DELETE FROM session_summary WHERE session_id=? AND upto_id>=?", (sid, from_message_id))
    update_session(sid)


# ---- messages ----
def add_message(session_id, role, content="", reasoning=None, attachments=None,
                tool_calls=None, tool_call_id=None, name=None):
    mid = _ins(
        "INSERT INTO messages(session_id,role,content,reasoning,attachments,tool_calls,tool_call_id,name,created)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (session_id, role, content, reasoning,
         json.dumps(attachments) if attachments else None,
         json.dumps(tool_calls) if tool_calls else None,
         tool_call_id, name, time.time()),
    )
    update_session(session_id)
    return mid


def get_messages(session_id):
    rows = _q("SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,))
    for r in rows:
        r["attachments"] = json.loads(r["attachments"]) if r["attachments"] else []
        r["tool_calls"] = json.loads(r["tool_calls"]) if r["tool_calls"] else []
    return rows


# ---- attachments ----
def add_attachment(filename, mime, kind, path, text, size):
    aid = uuid.uuid4().hex
    _ins("INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?)",
         (aid, filename, mime, kind, path, text, size, time.time()))
    return get_attachment(aid)


def get_attachment(aid):
    return _q("SELECT * FROM attachments WHERE id=?", (aid,), one=True)


# ---- memory ----
def add_memory(content):
    return _ins("INSERT INTO memories(content,created) VALUES(?,?)", (content, time.time()))


def list_memories(limit=200):
    return _q("SELECT * FROM memories ORDER BY id DESC LIMIT ?", (limit,))


def search_memories(query, limit=20):
    words = [w for w in query.lower().split() if len(w) > 2] or [query.lower()]
    rows = list_memories(1000)
    scored = [(sum(w in r["content"].lower() for w in words), r) for r in rows]
    return [r for s, r in sorted(scored, key=lambda x: -x[0]) if s > 0][:limit]


def delete_memory(mid):
    _q("DELETE FROM memories WHERE id=?", (mid,))
