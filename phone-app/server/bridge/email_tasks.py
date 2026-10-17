"""Suggested tasks from email: the loaded model reads recent Gmail and proposes to-dos; the user accepts or dismisses.

Nothing becomes a real task until the user taps "Add to my tasks" in the app. Emails already scanned are remembered,
so a new scan only reads new mail. The scan runs in the background; the app polls /api/email_tasks/status.
"""
import asyncio
import datetime as dt
import json
import re
import time

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import db, google_api, organizer
from .config import config, llm_api_base

db._conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS email_task_suggestions(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, notes TEXT, due TEXT,
        priority TEXT, email_id TEXT, email_subject TEXT, email_from TEXT, status TEXT DEFAULT 'new', created REAL);
    CREATE TABLE IF NOT EXISTS email_scanned(email_id TEXT PRIMARY KEY, scanned REAL);
    CREATE TABLE IF NOT EXISTS email_scanned_v2(email_id TEXT PRIMARY KEY, scanned REAL);
    """
)
try:   # task = something to do; reply = someone is waiting for the user's answer
    db._conn.execute("ALTER TABLE email_task_suggestions ADD COLUMN kind TEXT DEFAULT 'task'")
except Exception:
    pass
db._conn.commit()
SCANNED = "email_scanned_v2"    # v2 also looks for emails that need a reply, so older scans are read again once

router = APIRouter(prefix="/api/email_tasks")
job = {"running": False, "done": 0, "total": 0, "found": 0, "error": "", "finished": 0.0}
BATCH = 4


def _llm_headers():
    k = config.data.get("llm_api_key", "")
    return {"Authorization": f"Bearer {k}"} if k else {}


PROMPT = """You read the user's emails and find two kinds of items for THEM (not for other people):
- "task": something the user must do: pay, sign, submit, attend, prepare, register, renew, call someone, a deadline.
- "reply": a real person is waiting for the user's answer: asks the user a question, asks for information, a document,
  a decision, a confirmation or availability, or invites them and expects a response.
Ignore newsletters, ads, automatic notifications, no-reply senders and emails that need nothing. One email can give one
reply item and also task items. Today is {today}.
For each item give: "type" ("task" or "reply"), a short "title" starting with a verb in the email's language (for a reply:
"Reply to <name> about <topic>"), "due" YYYY-MM-DD if the email gives or implies one (else ""), "priority"
(high/normal/low) and a short "note" (for a reply: what exactly they ask for).
Answer ONLY with JSON: {{"tasks": [{{"email": <number>, "type": "task", "title": "...", "due": "", "priority": "normal", "note": "..."}}]}}
Use {{"tasks": []}} when there is nothing.

{emails}"""


async def _ask_model(client: httpx.AsyncClient, emails: list[dict]) -> list[dict]:
    text = "\n\n".join(f"### Email {i + 1}\nFrom: {e['from']}\nDate: {e['date']}\nSubject: {e['subject']}\n\n{e['body'][:2500]}"
                       for i, e in enumerate(emails))
    body = {"model": "local", "temperature": 0, "max_tokens": 1500, "stream": False,
            "messages": [{"role": "user", "content": PROMPT.format(today=dt.date.today().isoformat(), emails=text)}],
            "chat_template_kwargs": {"enable_thinking": False}, "response_format": {"type": "json_object"}}
    r = await client.post(llm_api_base() + "/chat/completions", json=body, headers=_llm_headers())
    if r.status_code == 400 and "response_format" in r.text:          # servers without JSON mode
        body.pop("response_format")
        r = await client.post(llm_api_base() + "/chat/completions", json=body, headers=_llm_headers())
    r.raise_for_status()
    out = r.json()["choices"][0]["message"]["content"] or ""
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return json.loads(m.group(0)).get("tasks", []) if m else []
    except (json.JSONDecodeError, AttributeError):
        return []


async def _scan(query: str, n: int):
    job.update(running=True, done=0, total=0, found=0, error="", finished=0.0)
    try:
        page = await asyncio.to_thread(google_api.gmail_page, query, "", n)
        seen = {r["email_id"] for r in db._q(f"SELECT email_id FROM {SCANNED}")}
        todo = [m for m in page["messages"] if m["id"] not in seen]
        job["total"] = len(todo)
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10)) as client:
            for i in range(0, len(todo), BATCH):
                batch = todo[i:i + BATCH]
                full = await asyncio.gather(*[asyncio.to_thread(google_api.gmail_read, m["id"]) for m in batch])
                for t in await _ask_model(client, full):
                    try:
                        e = full[int(t.get("email", 1)) - 1]
                    except (ValueError, IndexError, TypeError):
                        continue
                    title = str(t.get("title", "")).strip()
                    kind = "reply" if str(t.get("type", "")).lower().startswith("repl") else "task"
                    if not title or db._q("SELECT id FROM email_task_suggestions WHERE email_id=? AND (title=? OR (kind='reply' AND ?='reply'))",
                                          (e["id"], title, kind), one=True):
                        continue                        # already suggested from this email
                    db._ins("INSERT INTO email_task_suggestions(title,notes,due,priority,email_id,email_subject,email_from,status,created,kind)"
                            " VALUES(?,?,?,?,?,?,?,'new',?,?)",
                            (title[:160], str(t.get("note", ""))[:400], organizer._norm(str(t.get("due", "")) or None),
                             str(t.get("priority", "normal")).lower() if str(t.get("priority", "")).lower() in ("low", "high") else "normal",
                             e["id"], e["subject"][:200], e["from"][:200], time.time(), kind))
                    job["found"] += 1
                for e in full:
                    db._q(f"INSERT OR REPLACE INTO {SCANNED} VALUES(?,?)", (e["id"], time.time()))
                job["done"] = min(len(todo), i + BATCH)
    except httpx.HTTPError:
        job["error"] = "No model is answering on the PC. Load one from the Models screen, then scan again."
    except Exception as e:
        job["error"] = f"{type(e).__name__}: {e}"
    finally:
        job.update(running=False, finished=time.time())


class ScanIn(BaseModel):
    query: str = "in:inbox newer_than:14d"
    n: int = 30


@router.post("/scan")
async def scan(b: ScanIn):
    if not google_api.connected():
        raise HTTPException(400, "Connect Google first (Email tab)")
    if job["running"]:
        return job
    asyncio.create_task(_scan(b.query or "in:inbox newer_than:14d", max(1, min(b.n, 100))))
    await asyncio.sleep(0.2)
    return job


@router.get("/status")
async def status():
    return job


@router.get("")
async def suggestions(status: str = "new"):
    return db._q("SELECT * FROM email_task_suggestions WHERE status=? ORDER BY CASE WHEN due='' OR due IS NULL THEN 1 ELSE 0 END, due, id DESC",
                 (status,))


@router.post("/{sid}/accept")
async def accept(sid: int):
    s = db._q("SELECT * FROM email_task_suggestions WHERE id=?", (sid,), one=True)
    if not s:
        raise HTTPException(404)
    who = re.sub(r"\s*<.*?>", "", s["email_from"] or "").strip()
    note = (s["notes"] + "\n" if s["notes"] else "") + f"From email: \"{s['email_subject']}\" ({who})"
    t = organizer.task_save(s["title"], note, s["due"] or None, s["priority"], email_id=s["email_id"])
    db._q("UPDATE email_task_suggestions SET status='accepted' WHERE id=?", (sid,))
    return t


@router.post("/{sid}/dismiss")
async def dismiss(sid: int):
    db._q("UPDATE email_task_suggestions SET status='dismissed' WHERE id=?", (sid,))
    return {"ok": True}


@router.post("/forget")
async def forget():
    """Scan the same emails again next time (keeps decided suggestions)."""
    db._q(f"DELETE FROM {SCANNED}")
    db._q("DELETE FROM email_task_suggestions WHERE status='new'")
    return {"ok": True}
