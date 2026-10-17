"""Notes, tasks and calendar events, stored on the PC (SQLite), shared by the phone app and the model.

The phone shows them in the menu (Notes & tasks / Calendar); the model reads and writes them with tools, so the user
can ask "what tasks do I have this week?" or "remind me to call Sara on Friday". Calendar listings also include
Google Calendar events when Google is connected (google_api.py).
"""
import datetime as dt
import json
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import db

db._conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, created REAL, updated REAL);
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, notes TEXT, due TEXT,
        priority TEXT, done INTEGER DEFAULT 0, created REAL, done_at REAL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, start TEXT, "end" TEXT,
        location TEXT, notes TEXT, created REAL);
    """
)
db._conn.commit()

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- dates
def _parse(s: str | None) -> dt.datetime | None:
    """'2026-10-20', '2026-10-20 14:30', '2026-10-20T14:30:00', 'today', 'tomorrow' -> datetime (local time)."""
    if not s:
        return None
    s = str(s).strip().lower()
    today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if s in ("today", "now"):
        return today if s == "today" else dt.datetime.now()
    if s == "tomorrow":
        return today + dt.timedelta(days=1)
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s[:19].replace("z", ""), f)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


def _norm(s: str | None, date_only_ok=True) -> str:
    d = _parse(s)
    if not d:
        return ""
    return d.strftime("%Y-%m-%d") if date_only_ok and len(str(s).strip()) <= 10 and d.hour == d.minute == 0 \
        else d.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- storage
def notes_list(query: str = ""):
    rows = db._q("SELECT * FROM notes ORDER BY updated DESC")
    if query:
        words = [w for w in query.lower().split() if w]
        rows = [r for r in rows if all(w in f"{r['title']} {r['body']}".lower() for w in words)]
    return rows


def note_save(title: str, body: str = "", nid: int | None = None):
    now = time.time()
    if nid:
        db._q("UPDATE notes SET title=?, body=?, updated=? WHERE id=?", (title, body, now, nid))
        return db._q("SELECT * FROM notes WHERE id=?", (nid,), one=True)
    i = db._ins("INSERT INTO notes(title,body,created,updated) VALUES(?,?,?,?)", (title, body, now, now))
    return db._q("SELECT * FROM notes WHERE id=?", (i,), one=True)


def tasks_list(status: str = "open", due_before: str = ""):
    sql = "SELECT * FROM tasks" + {"open": " WHERE done=0", "done": " WHERE done=1"}.get(status, "")
    rows = db._q(sql + " ORDER BY done, CASE WHEN due='' OR due IS NULL THEN 1 ELSE 0 END, due, id")
    lim = _parse(due_before)
    if lim:
        if len(due_before.strip()) <= 10:
            lim = lim + dt.timedelta(days=1)            # "before 2026-10-20" includes that whole day
        rows = [r for r in rows if r["due"] and (_parse(r["due"]) or lim) < lim]
    for r in rows:
        r["done"] = bool(r["done"])
    return rows


def task_save(title: str | None = None, notes: str | None = None, due: str | None = None, priority: str | None = None,
              done: bool | None = None, tid: int | None = None):
    if tid:
        cur = db._q("SELECT * FROM tasks WHERE id=?", (tid,), one=True)
        if not cur:
            raise KeyError(f"No task with id {tid}")
        new = {"title": title if title is not None else cur["title"], "notes": notes if notes is not None else cur["notes"],
               "due": _norm(due) if due is not None else cur["due"], "priority": priority or cur["priority"],
               "done": int(done) if done is not None else cur["done"]}
        db._q("UPDATE tasks SET title=?, notes=?, due=?, priority=?, done=?, done_at=? WHERE id=?",
              (new["title"], new["notes"], new["due"], new["priority"], new["done"],
               time.time() if new["done"] and not cur["done"] else cur["done_at"], tid))
        r = db._q("SELECT * FROM tasks WHERE id=?", (tid,), one=True)
    else:
        i = db._ins("INSERT INTO tasks(title,notes,due,priority,done,created) VALUES(?,?,?,?,0,?)",
                    (title or "Task", notes or "", _norm(due), (priority or "normal").lower(), time.time()))
        r = db._q("SELECT * FROM tasks WHERE id=?", (i,), one=True)
    r["done"] = bool(r["done"])
    return r


def events_list(start: str = "", end: str = ""):
    a = _parse(start) or dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    b = _parse(end) or (a + dt.timedelta(days=30))
    if end and len(end.strip()) <= 10:
        b = b + dt.timedelta(days=1)
    rows = db._q('SELECT * FROM events ORDER BY start')
    out = []
    for r in rows:
        s = _parse(r["start"])
        if s and a <= s < b:
            out.append({**r, "source": "local"})
    return out


def event_save(title: str, start: str, end: str = "", location: str = "", notes: str = "", eid: int | None = None):
    s = _norm(start, date_only_ok=True)
    if not s:
        raise ValueError(f"Could not read the start time {start!r}; use YYYY-MM-DD HH:MM")
    e = _norm(end) if end else ""
    if eid:
        db._q('UPDATE events SET title=?, start=?, "end"=?, location=?, notes=? WHERE id=?', (title, s, e, location, notes, eid))
        i = eid
    else:
        i = db._ins('INSERT INTO events(title,start,"end",location,notes,created) VALUES(?,?,?,?,?,?)',
                    (title, s, e, location, notes, time.time()))
    return {**db._q("SELECT * FROM events WHERE id=?", (i,), one=True), "source": "local"}


def delete(kind: str, iid: int):
    table = {"notes": "notes", "tasks": "tasks", "events": "events"}[kind]
    db._q(f"DELETE FROM {table} WHERE id=?", (iid,))


# ---------------------------------------------------------------- model tools
def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


def tool_schemas() -> list[dict]:
    today = dt.date.today().isoformat()
    return [
        _fn("tasks_list", f"List the user's tasks / to-dos (today is {today}). Use it when the user asks what they have to do.",
            {"status": {"type": "string", "enum": ["open", "done", "all"], "description": "default open"},
             "due_before": {"type": "string", "description": "optional YYYY-MM-DD: only tasks due before the end of that day"}}, []),
        _fn("tasks_add", "Add a task / to-do / reminder for the user.",
            {"title": {"type": "string"}, "due": {"type": "string", "description": "YYYY-MM-DD or YYYY-MM-DD HH:MM (optional)"},
             "priority": {"type": "string", "enum": ["low", "normal", "high"]}, "notes": {"type": "string"}}, ["title"]),
        _fn("tasks_update", "Change a task: mark it done (done=true) or reopen it, rename it, or move its due date.",
            {"id": {"type": "integer"}, "done": {"type": "boolean"}, "title": {"type": "string"}, "due": {"type": "string"},
             "priority": {"type": "string", "enum": ["low", "normal", "high"]}, "notes": {"type": "string"}}, ["id"]),
        _fn("notes_add", "Save a note for the user (ideas, information, lists).",
            {"title": {"type": "string"}, "body": {"type": "string"}}, ["title"]),
        _fn("notes_search", "Find the user's saved notes (empty query = the latest notes).",
            {"query": {"type": "string"}}, []),
        _fn("calendar_list", f"List calendar events between two dates (today is {today}): the user's own calendar plus "
            "Google Calendar when connected. Use it for 'what do I have tomorrow / this week'.",
            {"start": {"type": "string", "description": "YYYY-MM-DD, default today"},
             "end": {"type": "string", "description": "YYYY-MM-DD, default 30 days later"}}, []),
        _fn("calendar_add", "Add an event to the user's calendar on this PC (use google_calendar_add for Google Calendar).",
            {"title": {"type": "string"}, "start": {"type": "string", "description": "YYYY-MM-DD HH:MM (or YYYY-MM-DD for all day)"},
             "end": {"type": "string"}, "location": {"type": "string"}, "notes": {"type": "string"}}, ["title", "start"]),
    ]


TOOL_NAMES = {"tasks_list", "tasks_add", "tasks_update", "notes_add", "notes_search", "calendar_list", "calendar_add"}


def _fmt_task(t):
    return (f"#{t['id']} [{'x' if t['done'] else ' '}] {t['title']}" + (f" (due {t['due']})" if t["due"] else "")
            + (f" !{t['priority']}" if t["priority"] and t["priority"] != "normal" else "") + (f" - {t['notes']}" if t["notes"] else ""))


def execute(name: str, a: dict) -> str:
    if name == "tasks_list":
        rows = tasks_list(a.get("status") or "open", a.get("due_before") or "")
        return "\n".join(_fmt_task(t) for t in rows) or "No tasks."
    if name == "tasks_add":
        return "Added " + _fmt_task(task_save(a.get("title"), a.get("notes"), a.get("due"), a.get("priority")))
    if name == "tasks_update":
        return "Updated " + _fmt_task(task_save(a.get("title"), a.get("notes"), a.get("due"), a.get("priority"),
                                                a.get("done"), int(a["id"])))
    if name == "notes_add":
        n = note_save(a.get("title") or "Note", a.get("body") or "")
        return f"Saved note #{n['id']}: {n['title']}"
    if name == "notes_search":
        rows = notes_list(a.get("query") or "")[:15]
        return "\n\n".join(f"#{n['id']} {n['title']}\n{(n['body'] or '')[:1500]}" for n in rows) or "No notes found."
    if name == "calendar_list":
        rows = all_events(a.get("start") or "", a.get("end") or "")
        return "\n".join(f"{e['start']}{' - ' + e['end'] if e.get('end') else ''}  {e['title']}"
                         f"{' @ ' + e['location'] if e.get('location') else ''}  [{e['source']}]" for e in rows) or "No events."
    if name == "calendar_add":
        e = event_save(a.get("title") or "Event", a.get("start") or "", a.get("end") or "", a.get("location") or "", a.get("notes") or "")
        return f"Added event #{e['id']}: {e['start']} {e['title']}"
    raise KeyError(name)


def all_events(start: str = "", end: str = "") -> list[dict]:
    """Local events plus Google Calendar ones (when connected), sorted by start."""
    rows = events_list(start, end)
    try:
        from . import google_api
        if google_api.connected():
            rows += google_api.calendar_events(start, end)
    except Exception as e:  # Google is optional: never break the local calendar
        rows.append({"id": 0, "title": f"(Google Calendar not available: {e})", "start": "", "end": "", "source": "google"})
    return sorted(rows, key=lambda e: e.get("start") or "")


# ---------------------------------------------------------------- REST for the phone app
class NoteIn(BaseModel):
    title: str
    body: str = ""


class TaskIn(BaseModel):
    title: str | None = None
    notes: str | None = None
    due: str | None = None
    priority: str | None = None
    done: bool | None = None


class EventIn(BaseModel):
    title: str
    start: str
    end: str = ""
    location: str = ""
    notes: str = ""


@router.get("/notes")
async def r_notes(q: str = ""):
    return notes_list(q)


@router.post("/notes")
async def r_note_add(b: NoteIn):
    return note_save(b.title, b.body)


@router.put("/notes/{nid}")
async def r_note_put(nid: int, b: NoteIn):
    return note_save(b.title, b.body, nid)


@router.get("/tasks_list")
async def r_tasks(status: str = "all"):
    return tasks_list(status)


@router.post("/tasks_list")
async def r_task_add(b: TaskIn):
    if not (b.title or "").strip():
        raise HTTPException(400, "title required")
    return task_save(b.title, b.notes, b.due, b.priority)


@router.patch("/tasks_list/{tid}")
async def r_task_patch(tid: int, b: TaskIn):
    try:
        return task_save(b.title, b.notes, b.due, b.priority, b.done, tid)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/events")
async def r_events(start: str = "", end: str = ""):
    return all_events(start, end)


@router.post("/events")
async def r_event_add(b: EventIn):
    try:
        return event_save(b.title, b.start, b.end, b.location, b.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/organizer/{kind}/{iid}")
async def r_delete(kind: str, iid: int):
    if kind not in ("notes", "tasks", "events"):
        raise HTTPException(404)
    delete(kind, iid)
    return {"ok": True}
