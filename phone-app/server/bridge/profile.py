"""Personal profile: what makes replies sound like the user wants, built from the user's own data instead of a fine-tune.

Once a day (and on demand) the model reads the user's recent messages (never temporary or vault chats), their notes and
saved memories, and writes a profile: writing style, preferences, recurring terms and key facts, plus a few short real
examples of the user's own writing. The profile goes into every chat's system prompt (it changes at most once a day, so
the prompt cache keeps working). The user can read, edit, switch off or rebuild it.
"""
import time

from fastapi import APIRouter
from pydantic import BaseModel

from . import db

router = APIRouter()
db._conn.execute("CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK (id = 1), text TEXT, enabled INTEGER, updated REAL, building INTEGER)")
db._conn.execute("INSERT OR IGNORE INTO profile VALUES(1, '', 1, 0, 0)")
db._conn.commit()


def get() -> dict:
    return db._q("SELECT * FROM profile WHERE id=1", one=True)


def prompt_block() -> str:
    p = get()
    if not p["enabled"] or not (p["text"] or "").strip():
        return ""
    return ("Personal profile of the user (built from their own messages; follow it when you write for them, and match "
            "their style when drafting in their name):\n" + p["text"].strip())


async def build() -> str:
    from . import research
    db._q("UPDATE profile SET building=1 WHERE id=1")
    try:
        msgs = db._q("SELECT m.content FROM messages m WHERE m.role='user' AND m.content <> '' AND m.created > ? AND "
                     "m.session_id NOT IN (SELECT session_id FROM session_kind) ORDER BY m.id DESC LIMIT 400",
                     (time.time() - 60 * 86400,))
        mine = "\n---\n".join(r["content"][:600] for r in msgs)[:30000]
        notes = "\n".join(f"- {r['title']}: {(r['body'] or '')[:300]}" for r in db._q(
            "SELECT title, body FROM notes ORDER BY id DESC LIMIT 40")) if _has("notes") else ""
        mems = "\n".join("- " + r["content"] for r in db._q("SELECT content FROM memories ORDER BY id DESC LIMIT 120")) if _has("memories") else ""
        if not mine.strip() and not mems.strip():
            return ""
        text = await research._llm([
            {"role": "system", "content": "You write a concise personal profile so an assistant can serve one user well."},
            {"role": "user", "content": "The user's own recent messages (newest first):\n" + mine + "\n\nTheir notes:\n" + notes[:6000] +
             "\n\nWhat the assistant already remembers about them:\n" + mems[:6000] + "\n\nWrite the profile in Markdown with these "
             "sections: ## Writing style (languages they use and when, tone, length, formatting they like or dislike); "
             "## Preferences (how they want answers: detail level, code style, units, etc.); ## Recurring topics and terms "
             "(their projects, tools, names, abbreviations with meanings); ## Key facts (stable facts useful in answers); "
             "## Examples of how they write (3-5 short verbatim quotes of their own messages that show the style). "
             "Be specific and short (under 450 words). Do not include passwords, keys, ID numbers or other secrets."}],
            1400, think=True)
        db._q("UPDATE profile SET text=?, updated=? WHERE id=1", (text.strip(), time.time()))
        return text
    finally:
        db._q("UPDATE profile SET building=0 WHERE id=1")


def _has(table: str) -> bool:
    return bool(db._q("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,), one=True))


async def daily():
    """Called by the background loop: rebuild once a day, at night (03:00-05:00) or when it is older than 2 days."""
    p = get()
    if not p["enabled"] or p["building"]:
        return
    age = time.time() - (p["updated"] or 0)
    if (3 <= time.localtime().tm_hour < 5 and age > 20 * 3600) or age > 2 * 86400:
        try:
            await build()
        except Exception as e:
            print("profile:", e)


class ProfileIn(BaseModel):
    enabled: bool = True
    text: str | None = None


@router.get("/api/profile")
async def profile_get():
    return get()


@router.put("/api/profile")
async def profile_set(b: ProfileIn):
    if b.text is not None:
        db._q("UPDATE profile SET text=?, updated=? WHERE id=1", (b.text, time.time()))
    db._q("UPDATE profile SET enabled=? WHERE id=1", (int(b.enabled),))
    return get()


@router.post("/api/profile/rebuild")
async def profile_rebuild():
    import asyncio
    if get()["building"]:
        return get()
    asyncio.create_task(build())
    return {**get(), "building": 1}
