"""Scheduled prompts ("every morning, summarize my unread email"), temperature alerts, and the notification feed the
phone app reads (it checks every 15 minutes in the background and right away when it is open).

A schedule runs its prompt as a normal chat turn in its own chat ("⏰ name"), with the access the user gave it (email,
tasks & calendar, web search). Code runs in the sandbox. Anything that needs approval (sending an email...) waits in that
chat until the user approves it, and the notification says so.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import db, models_ctl
from .config import config

router = APIRouter()

db._conn.executescript("""
CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, prompt TEXT, kind TEXT,
    at TEXT, every_min INTEGER, web INTEGER, email INTEGER, organizer INTEGER, enabled INTEGER, session_id TEXT,
    last_run REAL, next_run REAL, last_status TEXT, created REAL);
CREATE TABLE IF NOT EXISTS notify_events(id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, kind TEXT, title TEXT,
    body TEXT, session_id TEXT);
""")
db._conn.commit()


def notify(kind: str, title: str, body: str = "", session_id: str = ""):
    db._ins("INSERT INTO notify_events(created,kind,title,body,session_id) VALUES(?,?,?,?,?)",
            (time.time(), kind, title, body[:500], session_id))
    db._q("DELETE FROM notify_events WHERE created < ?", (time.time() - 14 * 86400,))


# ---------------------------------------------------------------- schedules
class ScheduleIn(BaseModel):
    name: str
    prompt: str
    kind: str = "daily"          # daily (at HH:MM) | every (every_min minutes)
    at: str = "08:00"
    every_min: int = 60
    web: bool = False
    email: bool = False
    organizer: bool = False
    enabled: bool = True
    project_id: int = 0          # a project's schedule: its runs are project chats (goal + notes in context)


def _next_run(kind: str, at: str, every_min: int, after: float) -> float:
    if kind == "every":
        return after + max(5, int(every_min)) * 60
    h, _, m = (at or "08:00").partition(":")
    base = datetime.fromtimestamp(after).replace(hour=int(h) % 24, minute=int(m or 0) % 60, second=0, microsecond=0)
    if base.timestamp() <= after:
        base += timedelta(days=1)
    return base.timestamp()


def _view(r: dict) -> dict:
    return {**r, "web": bool(r["web"]), "email": bool(r["email"]), "organizer": bool(r["organizer"]),
            "enabled": bool(r["enabled"])}


@router.get("/api/schedules")
async def schedules_list():
    return [_view(r) for r in db._q("SELECT * FROM schedules ORDER BY id")]


@router.post("/api/schedules")
async def schedules_add(b: ScheduleIn):
    if b.kind not in ("daily", "every"):
        raise HTTPException(400, "kind must be daily or every")
    i = db._ins("INSERT INTO schedules(name,prompt,kind,at,every_min,web,email,organizer,enabled,session_id,last_run,"
                "next_run,last_status,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (b.name.strip()[:80] or "Task", b.prompt, b.kind, b.at, b.every_min, int(b.web), int(b.email),
                 int(b.organizer), int(b.enabled), "", 0, _next_run(b.kind, b.at, b.every_min, time.time()), "",
                 time.time()))
    db._q("UPDATE schedules SET project_id=? WHERE id=?", (b.project_id, i))
    return _view(db._q("SELECT * FROM schedules WHERE id=?", (i,), one=True))


@router.put("/api/schedules/{sid}")
async def schedules_update(sid: int, b: ScheduleIn):
    if not db._q("SELECT id FROM schedules WHERE id=?", (sid,), one=True):
        raise HTTPException(404)
    db._q("UPDATE schedules SET name=?,prompt=?,kind=?,at=?,every_min=?,web=?,email=?,organizer=?,enabled=?,next_run=? "
          "WHERE id=?", (b.name.strip()[:80] or "Task", b.prompt, b.kind, b.at, b.every_min, int(b.web), int(b.email),
                         int(b.organizer), int(b.enabled), _next_run(b.kind, b.at, b.every_min, time.time()), sid))
    db._q("UPDATE schedules SET project_id=? WHERE id=?", (b.project_id, sid))
    return _view(db._q("SELECT * FROM schedules WHERE id=?", (sid,), one=True))


@router.delete("/api/schedules/{sid}")
async def schedules_delete(sid: int):
    db._q("DELETE FROM schedules WHERE id=?", (sid,))
    return {"ok": True}


@router.post("/api/schedules/{sid}/run")
async def schedules_run_now(sid: int):
    s = db._q("SELECT * FROM schedules WHERE id=?", (sid,), one=True)
    if not s:
        raise HTTPException(404)
    asyncio.create_task(_run_schedule(s))
    return {"ok": True}


async def _run_schedule(s: dict):
    from . import app as A          # the chat engine (imported late: app imports this module)
    sess = db.get_session(s["session_id"]) if s["session_id"] else None
    if not sess:
        sess = db.create_session("⏰ " + s["name"], "")
        db._q("UPDATE schedules SET session_id=? WHERE id=?", (sess["id"], s["id"]))
        if s.get("project_id"):
            from . import projects
            projects.link(sess["id"], s["project_id"])
    sid = sess["id"]
    if sid in A.runs:                # the previous run of this schedule is still going
        return
    db._q("UPDATE schedules SET last_run=?, next_run=?, last_status=? WHERE id=?",
          (time.time(), _next_run(s["kind"], s["at"], s["every_min"], time.time()), "running", s["id"]))
    db.add_message(sid, "user", s["prompt"])
    run = A.Run(sid, web=bool(s["web"]), email=bool(s["email"]), organizer=bool(s["organizer"]), sandbox=True)
    run.scheduled = True
    A.runs[sid] = run
    waiting = {"approval": False}

    def watch(ev):                   # tell the phone when the scheduled run needs the user
        if ev.get("type") == "approval_required" and not waiting["approval"]:
            waiting["approval"] = True
            notify("schedule", f"⏰ {s['name']}: needs your approval", "Open the chat to approve or deny.", sid)
    orig = run.emit
    run.emit = lambda ev: (watch(ev), orig(ev))[1]
    run.task = asyncio.create_task(A.chat_turn(run, None))
    try:
        await run.task
    except Exception:
        pass
    msgs = db.get_messages(sid)
    reply = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant" and m["content"]), "")
    err = next((e.get("message") for e in reversed(run.history) if e.get("type") == "error"), "")
    db._q("UPDATE schedules SET last_status=? WHERE id=?", ("error: " + err[:200] if err else "done", s["id"]))
    notify("schedule", f"⏰ {s['name']}" + (" failed" if err else ""), err or A._strip_think(reply)[:300], sid)


# ---------------------------------------------------------------- temperature alerts
class AlertsIn(BaseModel):
    gpu_c: float = 0          # 0 = off
    cpu_c: float = 0


@router.get("/api/alerts")
async def alerts_get():
    return {"gpu_c": config.data.get("alert_gpu_c", 0), "cpu_c": config.data.get("alert_cpu_c", 0)}


@router.post("/api/alerts")
async def alerts_set(b: AlertsIn):
    config["alert_gpu_c"] = max(0.0, b.gpu_c)
    config["alert_cpu_c"] = max(0.0, b.cpu_c)
    return await alerts_get()


_alert_state = {"gpu": 0.0, "cpu": 0.0}   # last alert time per sensor (0 = not alerting)


def _check_temp(name: str, value, limit: float):
    if not limit or value is None:
        return
    if value >= limit and time.time() - _alert_state[name] > 900:          # at most every 15 minutes
        _alert_state[name] = time.time()
        notify("temp", f"🌡 {name.upper()} is hot: {value:.0f} °C", f"Your alert threshold is {limit:.0f} °C.")
    elif value < limit - 5:
        _alert_state[name] = 0.0


# ---------------------------------------------------------------- notification feed
@router.get("/api/notify")
async def notify_feed(since: int = 0):
    rows = db._q("SELECT * FROM notify_events WHERE id > ? ORDER BY id LIMIT 50", (since,))
    last = db._q("SELECT MAX(id) AS m FROM notify_events", one=True)["m"] or 0
    return {"events": rows, "last_id": last}


# ---------------------------------------------------------------- background loop (started by app.py)
async def loop():
    await asyncio.sleep(20)
    while True:
        try:
            from . import privacy, profile
            privacy.cleanup_temp()
            await profile.daily()
            now = time.time()
            for s in db._q("SELECT * FROM schedules WHERE enabled=1 AND next_run <= ?", (now,)):
                asyncio.create_task(_run_schedule(s))
            if config.data.get("alert_gpu_c") or config.data.get("alert_cpu_c"):
                st = await models_ctl.status()
                _check_temp("gpu", st.get("gpu_temp"), float(config.data.get("alert_gpu_c") or 0))
                _check_temp("cpu", st.get("cpu_temp"), float(config.data.get("alert_cpu_c") or 0))
        except Exception as e:
            print("schedules loop:", e)
        await asyncio.sleep(30)
