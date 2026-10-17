"""Long-term memory for the personal assistant (mem0-style, all on the PC).

- Every memory gets a multilingual embedding (intfloat/multilingual-e5-large, run on the CPU with fastembed), so recall
  works by meaning, in Arabic and English ("أين أسكن؟" finds "The user lives in Thuwal").
- After each reply the model reviews the exchange and ADDs new lasting facts about the user, UPDATEs ones that changed
  and DELETEs ones that are no longer true (the mem0 method), instead of piling up duplicates.
- Each chat request gets the memories relevant to the current message (plus a few recent ones), not a fixed list.
- search_chats finds earlier conversations (episodic memory).
If fastembed or the model is not available yet (first start downloads ~2.2 GB), keyword search is used meanwhile.
"""
import asyncio
import json
import re
import threading
import time

import numpy as np

from . import db
from .config import DATA_DIR, config

MODEL = "intfloat/multilingual-e5-large"
CATEGORIES = ["personal", "family", "work", "preferences", "health", "places", "plans", "other"]

for col, ddl in (("category", "TEXT DEFAULT 'other'"), ("embedding", "BLOB"), ("updated", "REAL"), ("source", "TEXT DEFAULT 'manual'")):
    try:
        db._conn.execute(f"ALTER TABLE memories ADD COLUMN {col} {ddl}")
    except Exception:
        pass
db._conn.commit()

_model = None
_state = {"ready": False, "error": "", "loading": False}
_lock = threading.Lock()


# ---------------------------------------------------------------- embeddings
def _load():
    global _model
    with _lock:
        if _model is not None or _state["loading"]:
            return
        _state["loading"] = True
    try:
        import os
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL, cache_dir=str(DATA_DIR / "models"))
        _state["ready"] = True
        backfill()
    except Exception as e:
        _state["error"] = f"{type(e).__name__}: {e}"
    finally:
        _state["loading"] = False


def start():
    """Load the embedding model in the background (the server starts at once)."""
    threading.Thread(target=_load, daemon=True).start()


def _embed(texts: list[str], query: bool) -> np.ndarray | None:
    if not _state["ready"]:
        return None
    pre = "query: " if query else "passage: "
    v = np.array(list(_model.embed([pre + t for t in texts])), dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def backfill():
    rows = db._q("SELECT id, content FROM memories WHERE embedding IS NULL")
    for i in range(0, len(rows), 32):
        part = rows[i:i + 32]
        v = _embed([r["content"] for r in part], query=False)
        if v is None:
            return
        for r, e in zip(part, v):
            db._q("UPDATE memories SET embedding=? WHERE id=?", (e.tobytes(), r["id"]))


# ---------------------------------------------------------------- store / search
def _rows():
    return db._q("SELECT id, content, category, created, updated, source, embedding FROM memories ORDER BY id DESC")


def _public(r: dict, score: float | None = None) -> dict:
    d = {k: r[k] for k in ("id", "content", "category", "created", "updated", "source") if k in r}
    d["category"] = d.get("category") or "other"
    if score is not None:
        d["score"] = round(float(score), 3)
    return d


def search(query: str, k: int = 8, min_score: float = 0.0) -> list[dict]:
    """Best memories for a question: meaning (embeddings) plus a small boost for shared words."""
    rows = _rows()
    if not rows or not query.strip():
        return [_public(r) for r in rows[:k]]
    words = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 2}
    q = _embed([query], query=True)
    scored = []
    for r in rows:
        kw = sum(w in r["content"].lower() for w in words) / max(1, len(words)) if words else 0
        if q is not None and r["embedding"]:
            s = float(np.frombuffer(r["embedding"], dtype=np.float32) @ q[0]) + 0.05 * kw
        else:
            s = kw
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    best = scored[0][0]
    # e5 scores sit in a narrow band: keep the clearly related ones near the best match
    return [_public(r, s) for s, r in scored[:k] if s >= min_score and (q is None or s >= best - 0.08 or s >= 0.83)]


def add(content: str, category: str = "other", source: str = "manual") -> dict:
    """Save a fact; a near-duplicate of an existing memory replaces it instead of being added twice."""
    content = content.strip()
    if not content:
        raise ValueError("empty memory")
    cat = category if category in CATEGORIES else "other"
    v = _embed([content], query=False)
    if v is not None:
        for r in _rows():
            if r["embedding"] and float(np.frombuffer(r["embedding"], dtype=np.float32) @ v[0]) > 0.95:
                return update(r["id"], content, cat)
    now = time.time()
    i = db._ins("INSERT INTO memories(content, created, category, embedding, updated, source) VALUES(?,?,?,?,?,?)",
                (content, now, cat, v[0].tobytes() if v is not None else None, now, source))
    return _public(db._q("SELECT * FROM memories WHERE id=?", (i,), one=True))


def update(mid: int, content: str, category: str | None = None) -> dict:
    v = _embed([content], query=False)
    cur = db._q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
    if not cur:
        raise KeyError(f"No memory #{mid}")
    db._q("UPDATE memories SET content=?, category=?, embedding=?, updated=? WHERE id=?",
          (content.strip(), category if category in CATEGORIES else (cur.get("category") or "other"),
           v[0].tobytes() if v is not None else None, time.time(), mid))
    return _public(db._q("SELECT * FROM memories WHERE id=?", (mid,), one=True))


def delete(mid: int):
    db._q("DELETE FROM memories WHERE id=?", (mid,))


def list_all(query: str = "", category: str = "") -> list[dict]:
    rows = search(query, k=200) if query.strip() else [_public(r) for r in _rows()]
    return [r for r in rows if not category or r["category"] == category]


# ---------------------------------------------------------------- what the model sees
def context(message: str, recent: bool = True) -> str:
    """Memories related to a message (plus the newest ones when recent=True). Attached to the user message it was made
    for, so it never changes afterwards (that keeps llama.cpp's prompt cache valid)."""
    rel = search(message, k=10) if message.strip() else []
    seen = {m["id"] for m in rel}
    newest = [_public(r) for r in _rows()[:6] if r["id"] not in seen] if recent else []
    pick = rel + newest[: max(0, 14 - len(rel))]
    if not pick:
        return ""
    return ("what you remember about the user that may matter here:\n"
            + "\n".join(f"- [{m['category']}] {m['content']}" for m in pick))


# ---------------------------------------------------------------- automatic memory (mem0 method)
REVIEW = """You maintain the long-term memory of a personal assistant. Read the latest exchange and decide what to
remember about the USER for future conversations: lasting facts and preferences (name, family, people they know, work,
studies, projects, places, devices, health, habits, likes and dislikes, plans and important dates). Do NOT store
small talk, one-off requests, the assistant's own answers, temporary moods, or anything already in memory.
Write each memory as one short, self-contained sentence in the language the user used ("The user ..." / "المستخدم ...").
Compare with the existing memories: if a new fact replaces or corrects one, UPDATE it (same id); if the user says one is
no longer true, DELETE it. Categories: {cats}. Today is {today}.

Existing memories (id: text):
{existing}

Latest exchange:
USER: {user}
ASSISTANT: {assistant}

Answer ONLY with JSON: {{"add": [{{"text": "...", "category": "..."}}], "update": [{{"id": 0, "text": "..."}}], "delete": [0]}}
Use empty lists when nothing should change (that is the usual case)."""


async def review_turn(user: str, assistant: str):
    """Called after each finished reply (in the background): add / update / delete memories."""
    if not config.data.get("auto_memory", True) or len(user.strip()) < 8:
        return
    import datetime as dt
    import httpx
    from .config import llm_api_base
    related = await asyncio.to_thread(search, user + "\n" + assistant[:500], 10)
    existing = "\n".join(f"{m['id']}: {m['content']}" for m in related) or "(none yet)"
    body = {"model": "local", "temperature": 0, "max_tokens": 600, "stream": False,
            "messages": [{"role": "user", "content": REVIEW.format(cats=", ".join(CATEGORIES), today=dt.date.today().isoformat(),
                                                                    existing=existing, user=user[:3000], assistant=assistant[:2000])}],
            "chat_template_kwargs": {"enable_thinking": False}, "response_format": {"type": "json_object"}}
    key = config.data.get("llm_api_key", "")
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(llm_api_base() + "/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"} if key else {})
            if r.status_code == 400 and "response_format" in r.text:
                body.pop("response_format")
                r = await c.post(llm_api_base() + "/chat/completions", json=body)
        txt = r.json()["choices"][0]["message"]["content"] or ""
        m = re.search(r"\{.*\}", txt, re.S)
        ops = json.loads(m.group(0)) if m else {}
    except Exception:
        return
    ids = {x["id"] for x in related}
    for a in ops.get("add") or []:
        if isinstance(a, dict) and str(a.get("text", "")).strip():
            await asyncio.to_thread(add, str(a["text"]), str(a.get("category", "other")), "auto")
    for u in ops.get("update") or []:
        try:
            if int(u["id"]) in ids and str(u.get("text", "")).strip():
                await asyncio.to_thread(update, int(u["id"]), str(u["text"]))
        except (KeyError, ValueError, TypeError):
            continue
    for d in ops.get("delete") or []:
        try:
            if int(d) in ids:
                delete(int(d))
        except (ValueError, TypeError):
            continue


# ---------------------------------------------------------------- earlier conversations
def search_chats(query: str, limit: int = 8) -> str:
    """Find earlier chats by words (user and assistant messages), newest first, with the chat title and date."""
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2] or [query.lower()]
    rows = db._q("SELECT m.session_id, m.role, m.content, m.created, s.title FROM messages m JOIN sessions s ON s.id=m.session_id "
                 "WHERE m.role IN ('user','assistant') AND m.content <> '' ORDER BY m.id DESC LIMIT 4000")
    hits = []
    for r in rows:
        low = r["content"].lower()
        n = sum(w in low for w in words)
        if n:
            hits.append((n, r))
    hits.sort(key=lambda x: (-x[0], -x[1]["created"]))
    out, seen = [], set()
    for n, r in hits:
        if (r["session_id"], r["role"]) in seen:
            continue
        seen.add((r["session_id"], r["role"]))
        i = max(0, min(r["content"].lower().find(words[0]), len(r["content"]) - 300))
        when = time.strftime("%Y-%m-%d", time.localtime(r["created"]))
        out.append(f"[{when}] chat \"{r['title']}\" ({r['role']}): …{r['content'][max(0, i - 80):i + 300].strip()}…")
        if len(out) >= limit:
            break
    return "\n\n".join(out) or "No earlier chat mentions that."


def status() -> dict:
    n = db._q("SELECT COUNT(*) AS n, SUM(embedding IS NOT NULL) AS e FROM memories", one=True)
    return {"model": MODEL, "ready": _state["ready"], "loading": _state["loading"], "error": _state["error"],
            "count": n["n"] or 0, "embedded": n["e"] or 0, "auto_memory": config.data.get("auto_memory", True)}
