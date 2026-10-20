"""Long-term projects: a goal, living notes and a folder that every chat of the project shares.

Chats started in a project get the project (goal, notes, folder) in their context, and a `project_note` tool to record
progress, decisions and next steps in the project notes, so the next chat - or a scheduled run ("every evening, continue
the report") - picks up where the last one stopped. Files go to workspace/projects/<name>.

Project knowledge: files the user adds (PDF, Word, PowerPoint, Excel, text / code, figures) live in
<folder>/knowledge. Their text is extracted once (knowledge/.text), every project chat sees the list with a short
preview, and the `project_knowledge` tool searches or reads them in full. Figures carry the user's description.
"""
import asyncio
import json
import re
import time
import zipfile
from html import unescape
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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


class ChatIn(BaseModel):
    title: str = ""


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
            "project_note (one short paragraph), so later chats and scheduled runs continue from there."
            + knowledge_block(p))


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


# ------------------------------------------------------------------ knowledge
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}
PREVIEW_TOTAL = 9000          # characters of previews put in every project chat's prompt
READ_PAGE = 12000             # characters per project_knowledge read


def kdir(p: dict) -> Path:
    d = Path(p["folder"]) / "knowledge"
    (d / ".text").mkdir(parents=True, exist_ok=True)
    return d


def _meta(p: dict) -> dict:
    try:
        return json.loads((kdir(p) / ".meta.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_meta(p: dict, m: dict):
    (kdir(p) / ".meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def _xml_text(xml: str) -> str:
    xml = re.sub(r"</w:p>|</a:p>|<w:br/>|</row>|<w:tab/>", "\n", xml)
    return unescape(re.sub(r"<[^>]+>", "", xml))


def extract(path: Path) -> str:
    """Plain text of a knowledge file ("" for figures and unknown binary files)."""
    ext = path.suffix.lower()
    from . import tools
    if ext == ".pdf":
        return tools.extract_pdf_text(path, max_chars=2_000_000)
    if ext in IMAGE_EXT:
        return ""
    if ext in (".docx", ".pptx", ".xlsx"):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if ext == ".docx":
                parts = [n for n in names if n == "word/document.xml"]
            elif ext == ".pptx":
                parts = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                               key=lambda n: int(re.findall(r"\d+", n)[-1]))
            else:
                parts = [n for n in names if n == "xl/sharedStrings.xml"]
            out = []
            for i, n in enumerate(parts):
                txt = _xml_text(z.read(n).decode("utf-8", "replace"))
                out.append((f"--- slide {i + 1} ---\n" if ext == ".pptx" else "") + txt)
            return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    raw = path.read_bytes()[:3_000_000]
    if b"\x00" in raw[:4096]:
        return ""                    # binary file we cannot read
    return raw.decode("utf-8", "replace")


def knowledge(p: dict) -> list[dict]:
    d, m = kdir(p), _meta(p)
    out = []
    for f in sorted((x for x in d.iterdir() if x.is_file() and not x.name.startswith(".")), key=lambda x: x.name.lower()):
        tf = d / ".text" / (f.name + ".txt")
        chars = tf.stat().st_size if tf.exists() else 0
        out.append({"name": f.name, "size": f.stat().st_size, "chars": chars,
                    "kind": "figure" if f.suffix.lower() in IMAGE_EXT else "text" if chars else "file",
                    "description": m.get(f.name, "")})
    return out


def _text(p: dict, name: str) -> str:
    tf = kdir(p) / ".text" / (Path(name).name + ".txt")
    return tf.read_text(encoding="utf-8", errors="replace") if tf.exists() else ""


def knowledge_block(p: dict) -> str:
    items = knowledge(p)
    if not items:
        return ""
    d = kdir(p)
    per = max(600, PREVIEW_TOTAL // max(1, sum(1 for k in items if k["kind"] == "text")))
    lines = ["\n\nProject knowledge (files the user added as reference - use them when relevant, and say which file "
             "you used). Search or read them in full with project_knowledge; show a figure with "
             f"send_file_to_user and its path. Folder: {d}"]
    for k in items:
        if k["kind"] == "figure":
            lines.append(f"- FIGURE {k['name']}" + (f": {k['description']}" if k["description"] else " (no description)"))
        elif k["kind"] == "text":
            prev = re.sub(r"\s+", " ", _text(p, k["name"])[:per]).strip()
            lines.append(f"- {k['name']} ({k['chars']:,} characters)" + (f" - {k['description']}" if k["description"] else "")
                         + f"\n  starts: {prev}…")
        else:
            lines.append(f"- {k['name']} (no readable text)" + (f": {k['description']}" if k["description"] else ""))
    return "\n".join(lines)


def knowledge_tool_schema() -> dict:
    from . import tools
    return tools._fn("project_knowledge", "Search or read the project's knowledge files. Give `query` to find the "
                     "passages that match (keywords, any language), or `name` to read one file (use `start` to continue "
                     "where the last read stopped).",
                     {"query": {"type": "string"}, "name": {"type": "string"}, "start": {"type": "integer"}}, [])


def knowledge_tool(sid: str, args: dict) -> str:
    p = of_session(sid)
    if not p:
        return "This chat is not part of a project."
    items = knowledge(p)
    if not items:
        return "This project has no knowledge files."
    name = str(args.get("name") or "").strip()
    if name:
        k = next((k for k in items if k["name"].lower() == name.lower()), None) or \
            next((k for k in items if name.lower() in k["name"].lower()), None)
        if not k:
            return "No such file. Files: " + ", ".join(k["name"] for k in items)
        if k["kind"] == "figure":
            return f"{k['name']} is a figure: {k['description'] or 'no description'}. Path: {kdir(p) / k['name']}"
        txt, start = _text(p, k["name"]), max(0, int(args.get("start") or 0))
        part = txt[start:start + READ_PAGE]
        more = f"\n[... {len(txt) - start - len(part):,} more characters: read again with start={start + len(part)}]" \
            if start + len(part) < len(txt) else ""
        return f"{k['name']} (characters {start:,}-{start + len(part):,} of {len(txt):,}):\n{part}{more}"
    words = [w for w in re.findall(r"\w{3,}", str(args.get("query") or "").lower())]
    if not words:
        return "Give a query or a file name. Files: " + ", ".join(k["name"] for k in items)
    hits = []
    for k in items:
        if k["kind"] == "figure":
            score = sum(w in (k["name"] + " " + k["description"]).lower() for w in words)
            if score:
                hits.append((score + 1, k["name"], f"FIGURE: {k['description']}"))
            continue
        txt = _text(p, k["name"])
        for i in range(0, len(txt), 1200):
            chunk = txt[i:i + 1500]
            low = chunk.lower()
            score = sum(low.count(w) for w in words) + 2 * sum(w in low for w in words)
            if score:
                hits.append((score, k["name"], f"(at {i:,}) " + re.sub(r"\s+", " ", chunk)))
    if not hits:
        return "Nothing matched. Files: " + ", ".join(k["name"] for k in items)
    hits.sort(key=lambda h: -h[0])
    return "\n\n".join(f"[{n}] {c}" for _, n, c in hits[:6])


def _view(p: dict) -> dict:
    chats = db._q("SELECT s.id, s.title, s.updated FROM project_sessions ps JOIN sessions s ON s.id = ps.session_id "
                  "WHERE ps.project_id=? ORDER BY s.updated DESC", (p["id"],))
    files = []
    f = Path(p["folder"])
    if f.exists():
        files = sorted((x.name for x in f.iterdir() if x.is_file()), key=str.lower)[:200]
    return {**p, "chats": chats, "files": files, "knowledge": knowledge(p) if f.exists() else []}


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
async def projects_new_chat(pid: int, b: ChatIn | None = None):
    p = get(pid)
    if not p:
        raise HTTPException(404)
    title = (b.title.strip() if b else "")[:80]
    s = db.create_session(f"📁 {title or p['name']}", "")
    link(s["id"], pid)
    db._q("UPDATE projects SET updated=? WHERE id=?", (time.time(), pid))
    return s



@router.post("/api/projects/{pid}/knowledge")
async def knowledge_add(pid: int, file: UploadFile = File(...), description: str = Form("")):
    p = get(pid)
    if not p:
        raise HTTPException(404)
    name = re.sub(r"[^\w.\- ()]", "_", Path(file.filename or "file").name)[:120].lstrip(".") or "file"
    dest = kdir(p) / name
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > 100 * 1024 * 1024:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File too large (100 MB max)")
            out.write(chunk)
    try:
        text = await asyncio.to_thread(extract, dest)
    except Exception as e:
        text = ""
        description = description or f"(could not read: {type(e).__name__})"
    tf = kdir(p) / ".text" / (name + ".txt")
    if text.strip():
        tf.write_text(text, encoding="utf-8")
    else:
        tf.unlink(missing_ok=True)
    m = _meta(p)
    if description.strip():
        m[name] = description.strip()[:500]
    _save_meta(p, m)
    db._q("UPDATE projects SET updated=? WHERE id=?", (time.time(), pid))
    return next(k for k in knowledge(p) if k["name"] == name)


@router.put("/api/projects/{pid}/knowledge/{name}")
async def knowledge_describe(pid: int, name: str, b: ChatIn):
    p = get(pid)
    if not p or not (kdir(p) / Path(name).name).is_file():
        raise HTTPException(404)
    m = _meta(p)
    m[Path(name).name] = b.title.strip()[:500]     # ChatIn.title carries the description
    _save_meta(p, m)
    return {"ok": True}


@router.delete("/api/projects/{pid}/knowledge/{name}")
async def knowledge_delete(pid: int, name: str):
    p = get(pid)
    if not p:
        raise HTTPException(404)
    n = Path(name).name
    (kdir(p) / n).unlink(missing_ok=True)
    (kdir(p) / ".text" / (n + ".txt")).unlink(missing_ok=True)
    m = _meta(p)
    m.pop(n, None)
    _save_meta(p, m)
    return {"ok": True}
