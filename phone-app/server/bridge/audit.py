"""Audit log: every action the AI takes with tools - what, when, in which chat, whether it needed and got approval, and
the result - so the user can check what happened on the PC (the app's Audit log screen)."""
import json
import time

from fastapi import APIRouter

from . import db

router = APIRouter()
SKIP = {"update_tasks"}                       # bookkeeping only

db._conn.execute("""CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, session_id TEXT,
    tool TEXT, summary TEXT, approval TEXT, ok INTEGER, result TEXT, source TEXT)""")
db._conn.commit()


def _summary(tool: str, args: dict) -> str:
    a = args or {}
    if tool == "run_code":
        code = str(a.get("code", "")).strip().splitlines()
        return f"{a.get('language', 'python')}: " + (code[0][:140] if code else "") + (f" (+{len(code) - 1} lines)" if len(code) > 1 else "")
    for k in ("path", "target", "source", "name", "query", "url", "to", "subject", "title", "question", "content", "text", "root"):
        if a.get(k):
            return f"{k}: {str(a[k])[:160]}"
    return json.dumps(a, ensure_ascii=False)[:160]


def log(session_id: str, tool: str, args: dict, approval: str, result: str, source: str = "chat"):
    if tool in SKIP:
        return
    from . import privacy
    if session_id and privacy.kind(session_id) == "vault":   # never write vault contents into the log
        args, result = {}, "(private vault chat)"
    r = str(result or "")
    bad = r.startswith(("Error", "OCR failed", "Access denied", "The user denied")) or '"exit_code": -' in r[:200] or \
        ('"exit_code": ' in r[:200] and '"exit_code": 0' not in r[:200])
    try:
        db._ins("INSERT INTO audit(ts,session_id,tool,summary,approval,ok,result,source) VALUES(?,?,?,?,?,?,?,?)",
                (time.time(), session_id, tool, _summary(tool, args), approval, 0 if bad else 1, r[:400], source))
        db._q("DELETE FROM audit WHERE ts < ?", (time.time() - 180 * 86400,))   # keep half a year
    except Exception as e:
        print("audit:", e)


@router.get("/api/audit")
async def audit_list(q: str = "", tool: str = "", limit: int = 200):
    sql, args = "SELECT a.*, s.title AS chat FROM audit a LEFT JOIN sessions s ON s.id = a.session_id WHERE 1=1", []
    if tool:
        sql += " AND a.tool = ?"; args.append(tool)
    if q:
        sql += " AND (a.summary LIKE ? OR a.result LIKE ? OR a.tool LIKE ?)"; args += [f"%{q}%"] * 3
    sql += " ORDER BY a.id DESC LIMIT ?"; args.append(max(1, min(limit, 1000)))
    return db._q(sql, tuple(args))
