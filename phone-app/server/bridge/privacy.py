"""Temporary chats and the private vault.

Temporary chat: not kept. No memories are taken from it, it never shows up in chat search, and it is deleted when the
app leaves it (and at the latest 24 hours later).

Private vault: chats whose text is encrypted at rest (AES-256-GCM). The key is made on the phone, kept in Android's
keystore behind the fingerprint, and sent only while the vault is unlocked (header X-Vault-Key); the PC never stores it.
Without the key vault chats are hidden and unreadable - message text, reasoning, tool arguments, summaries. They are
never used for memories and their audit-log entries are masked. Files attached in the vault are stored like other
uploads (not encrypted).
"""
import base64
import json
import os
import time
from contextvars import ContextVar

from fastapi import APIRouter, HTTPException

from . import db

router = APIRouter()
vault_key: ContextVar[bytes | None] = ContextVar("vault_key", default=None)
PREFIX = "🔒v1:"
VAULT_TITLE = "🔒 Private chat"

db._conn.executescript("""
CREATE TABLE IF NOT EXISTS session_kind(session_id TEXT PRIMARY KEY, kind TEXT, created REAL);
CREATE TABLE IF NOT EXISTS vault_meta(k TEXT PRIMARY KEY, v TEXT);
""")
db._conn.commit()


def kind(sid: str) -> str:
    r = db._q("SELECT kind FROM session_kind WHERE session_id=?", (sid,), one=True)
    return r["kind"] if r else ""


def mark(sid: str, k: str):
    db._q("INSERT OR REPLACE INTO session_kind VALUES(?,?,?)", (sid, k, time.time()))


def is_private(sid: str) -> bool:
    return kind(sid) in ("temp", "vault")


# ---------------------------------------------------------------- encryption
def _aes():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM


def enc(text: str | None, key: bytes) -> str | None:
    if text is None or text == "":
        return text
    n = os.urandom(12)
    return PREFIX + base64.b64encode(n + _aes()(key).encrypt(n, text.encode("utf-8"), None)).decode()


def dec(text: str | None, key: bytes | None) -> str | None:
    if not text or not str(text).startswith(PREFIX):
        return text
    if not key:
        return "[locked - unlock the vault]"
    raw = base64.b64decode(text[len(PREFIX):])
    try:
        return _aes()(key).decrypt(raw[:12], raw[12:], None).decode("utf-8")
    except Exception:
        return "[wrong vault key]"


def check_key(key: bytes) -> bool:
    """The first unlock stores an encrypted check value; later keys must decrypt it."""
    r = db._q("SELECT v FROM vault_meta WHERE k='check'", one=True)
    if not r:
        db._q("INSERT INTO vault_meta VALUES('check', ?)", (enc("vault-ok", key),))
        return True
    return dec(r["v"], key) == "vault-ok"


def key_from_header(h: str | None) -> bytes | None:
    if not h:
        return None
    try:
        k = base64.b64decode(h)
    except Exception:
        return None
    return k if len(k) == 32 and check_key(k) else None


# ---------------------------------------------------------------- db hooks
_add, _get_msgs, _update, _list = db.add_message, db.get_messages, db.update_session, db.list_sessions
_set_summary, _get_summary = db.set_summary, db.get_summary


def add_message(session_id, role, content="", reasoning=None, attachments=None, tool_calls=None, tool_call_id=None, name=None):
    if kind(session_id) == "vault":
        k = vault_key.get()
        if not k:
            raise HTTPException(423, "the vault is locked")
        content, reasoning = enc(content, k), enc(reasoning, k)
        if tool_calls:
            tool_calls = [{**tc, "function": {**tc.get("function", {}), "arguments": enc(tc.get("function", {}).get("arguments") or "{}", k)}}
                          for tc in tool_calls]
    return _add(session_id, role, content, reasoning, attachments, tool_calls, tool_call_id, name)


def get_messages(session_id):
    rows = _get_msgs(session_id)
    if kind(session_id) != "vault":
        return rows
    k = vault_key.get()
    for r in rows:
        r["content"], r["reasoning"] = dec(r["content"], k), dec(r["reasoning"], k)
        for tc in r["tool_calls"] or []:
            f = tc.get("function") or {}
            if f.get("arguments"):
                f["arguments"] = dec(f["arguments"], k) if k else "{}"
    return rows


def update_session(sid, **fields):
    if kind(sid) == "vault" and "title" in fields:
        fields["title"] = VAULT_TITLE      # the real topic never goes into the chat list
    return _update(sid, **fields)


def list_sessions():
    """Normal chat list: no vault chats (they are listed by /api/vault/sessions while unlocked)."""
    vault = {r["session_id"] for r in db._q("SELECT session_id FROM session_kind WHERE kind='vault'")}
    return [s for s in _list() if s["id"] not in vault]


def set_summary(sid, summary, upto_id):
    if kind(sid) == "vault" and vault_key.get():
        summary = enc(summary, vault_key.get())
    return _set_summary(sid, summary, upto_id)


def get_summary(sid):
    s = _get_summary(sid)
    if s and kind(sid) == "vault":
        s = {**s, "summary": dec(s["summary"], vault_key.get())}
    return s


db.add_message, db.get_messages, db.update_session, db.list_sessions = add_message, get_messages, update_session, list_sessions
db.set_summary, db.get_summary = set_summary, get_summary


def cleanup_temp(max_age_h: float = 24):
    for r in db._q("SELECT session_id FROM session_kind WHERE kind='temp' AND created < ?", (time.time() - max_age_h * 3600,)):
        db.delete_session(r["session_id"])
        db._q("DELETE FROM session_kind WHERE session_id=?", (r["session_id"],))


# ---------------------------------------------------------------- routes
@router.post("/api/sessions/temp")
async def temp_session():
    s = db.create_session("⏳ Temporary chat", "")
    mark(s["id"], "temp")
    return s


@router.post("/api/vault/unlock")
async def vault_unlock():
    if not vault_key.get():
        raise HTTPException(403, "wrong or missing vault key")
    return {"ok": True}


@router.get("/api/vault/sessions")
async def vault_sessions():
    if not vault_key.get():
        raise HTTPException(423, "the vault is locked")
    ids = {r["session_id"] for r in db._q("SELECT session_id FROM session_kind WHERE kind='vault'")}
    out = []
    for s in _list():
        if s["id"] in ids:
            first = next((m["content"] for m in get_messages(s["id"]) if m["role"] == "user"), "")
            out.append({**s, "title": "🔒 " + (first or "Private chat").replace("\n", " ")[:48]})
    return out


@router.post("/api/vault/sessions")
async def vault_new():
    if not vault_key.get():
        raise HTTPException(423, "the vault is locked")
    s = db.create_session(VAULT_TITLE, "")
    mark(s["id"], "vault")
    return s
