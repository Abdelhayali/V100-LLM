"""Long-term projects: a goal, living notes and a folder that every chat of the project shares.

Chats started in a project get the project (goal, notes, folder) in their context, and a `project_note` tool to record
progress, decisions and next steps in the project notes, so the next chat - or a scheduled run ("every evening, continue
the report") - picks up where the last one stopped. Files go to workspace/projects/<name>.
"""
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import db
from .config import config

router = APIRouter()
db._conn.executescript("""
CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, goal TEXT, notes TEXT,
    folder TEXT, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS project_sessions(session_id TEXT PRIMARY KEY, project_id INTEGER);
""")
try:
    db._conn.execute("ALTER TABLE schedules ADD COLUMN project_id INTEGER DEFAULT 0")
except Exception:
    pass   # already there
db._conn.commit()
MAX_NOTES = 12000


class ProjectIn(BaseModel):
    name: str
    goal: str = ""
    notes: str = ""


def get(pid: int) -> dict | None:
    return db._q("SELECT * FROM projects WHERE id=?", (pid,), one=True)


def of_session(sid: str) -> dict | None:
    r = db._q("SELECT project_id FROM project_sessions WHERE session_id=?", (sid,), one=True)
    return get(r["project_id"]) if r else None


def link(sid: str, pid: int):
    db._q("INSERT OR REPLACE INTO project_sessions VALUES(?,?)", (sid, pid))


def context(sid: str) -> str:
    """The project block added to the system prompt of a project chat."""
    p = of_session(sid)
    if not p:
        return ""
    return (f"This chat belongs to the user's long-term project \"{p['name']}\".\nGoal: {p['goal'] or '(not set)'}\n"
            f"Project folder (save the project's files here): {p['folder']}\n"
            f"Project notes so far (progress, decisions, next steps):\n{p['notes'] or '(none yet)'}\n"
            "Work towards the goal. When you make progress, decide something or find the next steps, record it with "
            "project_note (one short paragraph), so later chats and scheduled runs continue from there.")


def note_tool_schema() -> dict:
    from . import tools
    return tools._fn("project_note", "Add a short entry to this project's notes: progress made, a decision, a result "
                     "file, or the next steps. Keep entries short; they are read by every later chat of the project.",
                     {"text": {"type": "string"}}, ["text"])


def add_note(sid: str, text: str) -> str:
    p = of_session(sid)
    if not p:
        return "This chat is not part of a project."
    entry = f"[{time.strftime('%Y-%m-%d %H:%M')}] {text.strip()}"
    notes = ((p["notes"] or "") + "\n" + entry).strip()
    if len(notes) > MAX_NOTES:              # keep the newest notes
        notes = "…\n" + notes[-MAX_NOTES:]
    db._q("UPDATE projects SET notes=?, updated=? WHERE id=?", (notes, time.time(), p["id"]))
    return f"Saved to the notes of project {p['name']}."


def _view(p: dict) -> dict:
    chats = db._q("SELECT s.id, s.title, s.updated FROM project_sessions ps JOIN sessions s ON s.id = ps.session_id "
                  "WHERE ps.project_id=? ORDER BY s.updated DESC", (p["id"],))
    files = []
    f = Path(p["folder"])
    if f.exists():
        files = sorted((x.name for x in f.iterdir() if x.is_file()), key=str.lower)[:200]
    return {**p, "chats": chats, "files": files}


@router.get("/api/projects")
async def projects_list():
    return [_view(p) for p in db._q("SELECT * FROM projects ORDER BY updated DESC")]


@router.post("/api/projects")
async def projects_add(b: ProjectIn):
    name = b.name.strip()[:80]
    if not name:
        raise HTTPException(400, "name required")
    folder = Path(config["workspace"]) / "projects" / (re.sub(r"[^\w\-]+", "-", name).strip("-") or f"project-{int(time.time())}")
    folder.mkdir(parents=True, exist_ok=True)
    i = db._ins("INSERT INTO projects(name,goal,notes,folder,created,updated) VALUES(?,?,?,?,?,?)",
                (name, b.goal, b.notes, str(folder), time.time(), time.time()))
    return _view(get(i))


@router.put("/api/projects/{pid}")
async def projects_update(pid: int, b: ProjectIn):
    if not get(pid):
        raise HTTPException(404)
    db._q("UPDATE projects SET name=?, goal=?, notes=?, updated=? WHERE id=?", (b.name.strip()[:80], b.goal, b.notes, time.time(), pid))
    return _view(get(pid))


@router.delete("/api/projects/{pid}")
async def projects_delete(pid: int):
    db._q("DELETE FROM project_sessions WHERE project_id=?", (pid,))
    db._q("DELETE FROM projects WHERE id=?", (pid,))
    return {"ok": True}   # the folder and chats stay


@router.post("/api/projects/{pid}/chat")
async def projects_new_chat(pid: int):
    p = get(pid)
    if not p:
        raise HTTPException(404)
    s = db.create_session(f"📁 {p['name']}", "")
    link(s["id"], pid)
    db._q("UPDATE projects SET updated=? WHERE id=?", (time.time(), pid))
    return s
