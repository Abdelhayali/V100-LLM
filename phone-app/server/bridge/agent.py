"""BETA: OpenCode coding agent, driven from the phone.

The bridge runs a private `opencode serve` (password protected, localhost only) configured to use the
local LLM, and exposes a small API: create an agent session in a project folder, send tasks, stream
its progress, answer its permission requests (edits, shell commands), abort it and see its changes.
"""
import asyncio
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import db, tools
from .config import DATA_DIR, config, llm_api_base

router = APIRouter(prefix="/api/agent")

db._conn.execute("CREATE TABLE IF NOT EXISTS agent_sessions("
                 "id TEXT PRIMARY KEY, directory TEXT, title TEXT, created REAL, updated REAL)")
db._conn.commit()


# ---------------------------------------------------------------- the private OpenCode server
def find_opencode() -> str | None:
    if config.data.get("opencode_path") and Path(config["opencode_path"]).is_file():
        return config["opencode_path"]
    exe = shutil.which("opencode.exe")
    if exe:
        return exe
    shim = shutil.which("opencode")  # npm installs a .cmd shim next to node_modules
    if shim:
        real = Path(shim).parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
        if real.is_file():
            return str(real)
    return None


class OpenCode:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.password = secrets.token_urlsafe(24)
        self.port = int(config.data.get("opencode_port") or 4196)
        self.base = f"http://127.0.0.1:{self.port}"
        self.lock = asyncio.Lock()
        self.model = ""

    @property
    def auth(self):
        return ("opencode", self.password)

    def client(self, timeout=30) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base, auth=self.auth, timeout=timeout)

    async def write_config(self) -> Path:
        """OpenCode config generated from the bridge settings (LLM URL, models, context size)."""
        from .app import context_size, list_models
        try:
            models = await list_models()
        except Exception:
            models = []
        self.model = config["default_model"] or (models[0] if models else "local-model")
        if self.model not in models:
            models.insert(0, self.model)
        ctx = await context_size() or 32768
        out_tokens = int(config.data.get("max_tokens") or 16384)
        cfg = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {"local": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Local LLM (LocalAI Bridge)",
                "options": {"baseURL": llm_api_base()},
                "models": {m: {"name": m.split("\\")[-1].split("/")[-1], "tool_call": True,
                               "limit": {"context": ctx, "output": min(out_tokens, ctx // 2)}} for m in models},
            }},
            "model": f"local/{self.model}",
            "small_model": f"local/{self.model}",
            # every file edit, shell command and web fetch is sent to the phone for approval
            "permission": {"edit": "ask", "bash": "ask", "webfetch": "ask"},
            "share": "disabled",
            "autoupdate": False,
        }
        path = DATA_DIR / "opencode" / "opencode.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return path

    async def healthy(self) -> bool:
        try:
            async with self.client(3) as c:
                return (await c.get("/global/health")).status_code == 200
        except Exception:
            return False

    async def ensure(self):
        """Start `opencode serve` if it isn't running."""
        async with self.lock:
            if self.proc and self.proc.poll() is None and await self.healthy():
                return
            exe = find_opencode()
            if not exe:
                raise HTTPException(503, "OpenCode is not installed on the PC (npm install -g opencode-ai)")
            cfg_path = await self.write_config()
            env = {**os.environ, "OPENCODE_CONFIG": str(cfg_path), "OPENCODE_SERVER_PASSWORD": self.password}
            log = open(DATA_DIR / "opencode" / "opencode.log", "w", encoding="utf-8")
            self.proc = subprocess.Popen(
                [exe, "serve", "--port", str(self.port), "--hostname", "127.0.0.1"],
                cwd=str(DATA_DIR / "opencode"), env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            from .tunnel import _job  # dies together with the bridge
            if _job:
                try:
                    _job.add(self.proc)
                except Exception:
                    pass
            for _ in range(60):
                if await self.healthy():
                    return
                if self.proc.poll() is not None:
                    break
                await asyncio.sleep(0.5)
            raise HTTPException(503, "OpenCode did not start (see server/data/opencode/opencode.log)")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()


oc = OpenCode()


# ---------------------------------------------------------------- helpers
def _session_row(sid: str) -> dict:
    r = db._q("SELECT * FROM agent_sessions WHERE id=?", (sid,), one=True)
    if not r:
        raise HTTPException(404, "Unknown agent session")
    return r


def _short(v, n):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + f"… [{len(s) - n} more chars]"


def simplify_part(p: dict) -> dict | None:
    t = p.get("type")
    if t in ("text", "reasoning"):
        return {"id": p["id"], "kind": t, "text": p.get("text", "")}
    if t == "tool":
        st = p.get("state") or {}
        inp = st.get("input") or {}
        meta = st.get("metadata") or {}
        return {"id": p["id"], "kind": "tool", "tool": p.get("tool", ""), "status": st.get("status", ""),
                "title": st.get("title") or "",
                "input": {k: _short(v, 1500) for k, v in inp.items()} if isinstance(inp, dict) else {},
                "output": _short(st.get("output") or "", 4000),
                "diff": _short(meta.get("diff") or "", 8000),
                "error": _short(st.get("error") or "", 1000)}
    return None


def simplify_permission(pr: dict) -> dict:
    meta = pr.get("metadata") or {}
    return {"id": pr.get("id"), "permission": pr.get("permission", ""), "patterns": pr.get("patterns") or [],
            "command": meta.get("command") or "", "filepath": meta.get("filepath") or "",
            "diff": _short(meta.get("diff") or "", 8000)}


async def _busy_map(directory: str) -> dict:
    async with oc.client(5) as c:
        r = await c.get("/session/status", params={"directory": directory})
        return r.json() if r.status_code == 200 else {}


# ---------------------------------------------------------------- API
class NewAgentSession(BaseModel):
    directory: str
    title: str = ""


class Prompt(BaseModel):
    text: str


class Reply(BaseModel):
    reply: str  # once | always | reject
    directory: str


@router.get("/status")
async def status():
    exe = find_opencode()
    return {"installed": bool(exe), "running": bool(oc.proc and oc.proc.poll() is None),
            "model": oc.model or config["default_model"]}


@router.get("/sessions")
async def list_sessions():
    return db._q("SELECT * FROM agent_sessions ORDER BY updated DESC")


@router.post("/sessions")
async def create_session(body: NewAgentSession):
    try:
        d = tools.resolve_path(body.directory)
    except tools.ToolError as e:
        raise HTTPException(403, str(e))
    if not d.is_dir():
        raise HTTPException(400, "Not a folder")
    await oc.ensure()
    title = body.title.strip() or d.name
    async with oc.client() as c:
        r = await c.post("/session", params={"directory": str(d)}, json={"title": title})
        r.raise_for_status()
        s = r.json()
    now = time.time()
    db._ins("INSERT INTO agent_sessions VALUES(?,?,?,?,?)", (s["id"], str(d), title, now, now))
    return {"id": s["id"], "directory": str(d), "title": title}


@router.delete("/sessions/{sid}")
async def delete_session(sid: str):
    row = _session_row(sid)
    try:
        await oc.ensure()
        async with oc.client() as c:
            await c.delete(f"/session/{sid}", params={"directory": row["directory"]})
    except Exception:
        pass
    db._q("DELETE FROM agent_sessions WHERE id=?", (sid,))
    return {"ok": True}


@router.get("/sessions/{sid}")
async def get_session(sid: str):
    row = _session_row(sid)
    await oc.ensure()
    P = {"directory": row["directory"]}
    async with oc.client() as c:
        msgs = (await c.get(f"/session/{sid}/message", params=P)).json()
        perms = (await c.get("/permission", params=P)).json()
    out, tokens = [], None
    for m in msgs:
        info = m.get("info", {})
        parts = [x for x in (simplify_part(p) for p in m.get("parts", [])) if x]
        if info.get("role") == "assistant" and info.get("tokens"):
            tokens = info["tokens"]
        out.append({"id": info.get("id"), "role": info.get("role"), "parts": parts})
    busy = sid in await _busy_map(row["directory"])
    return {**row, "messages": out, "busy": busy,
            "context_used": (tokens or {}).get("input"), "context_size": await _ctx(),
            "permissions": [simplify_permission(p) for p in perms if p.get("sessionID") == sid]}


async def _ctx():
    from .app import context_size
    return await context_size()


@router.post("/sessions/{sid}/prompt")
async def prompt(sid: str, body: Prompt):
    row = _session_row(sid)
    await oc.ensure()
    async with oc.client() as c:
        r = await c.post(f"/session/{sid}/prompt_async", params={"directory": row["directory"]}, json={
            "parts": [{"type": "text", "text": body.text}],
            "model": {"providerID": "local", "modelID": oc.model}})
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text[:300])
    db._q("UPDATE agent_sessions SET updated=? WHERE id=?", (time.time(), sid))
    return {"ok": True}


@router.post("/sessions/{sid}/abort")
async def abort(sid: str):
    row = _session_row(sid)
    await oc.ensure()
    async with oc.client() as c:
        await c.post(f"/session/{sid}/abort", params={"directory": row["directory"]})
    return {"ok": True}


@router.post("/permissions/{rid}")
async def reply_permission(rid: str, body: Reply):
    if body.reply not in ("once", "always", "reject"):
        raise HTTPException(400, "reply must be once, always or reject")
    await oc.ensure()
    async with oc.client() as c:
        r = await c.post(f"/permission/{rid}/reply", params={"directory": body.directory}, json={"reply": body.reply})
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:300])
    return {"ok": True}


@router.get("/sessions/{sid}/events")
async def events(sid: str, auto: bool = False):
    """Live progress of one agent session (SSE). auto=true approves permission requests automatically."""
    row = _session_row(sid)
    await oc.ensure()
    directory = row["directory"]
    part_kind: dict[str, str] = {}

    async def gen():
        q: asyncio.Queue = asyncio.Queue()

        async def pump():
            async with oc.client(None) as c:
                async with c.stream("GET", "/event", params={"directory": directory}) as r:
                    async for line in r.aiter_lines():
                        if line.startswith("data:"):
                            await q.put(json.loads(line[5:]))

        task = asyncio.create_task(pump())
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    if task.done():
                        yield f"data: {json.dumps({'type': 'error', 'message': 'lost connection to OpenCode'})}\n\n"
                        return
                    yield 'data: {"type": "ping"}\n\n'
                    continue
                t, pr = ev.get("type", ""), ev.get("properties", {}) or {}
                if (pr.get("sessionID") or (pr.get("part") or {}).get("sessionID")
                        or (pr.get("info") or {}).get("sessionID")) != sid:
                    continue
                out = None
                if t == "message.part.updated":
                    part = pr.get("part") or {}
                    part_kind[part.get("id", "")] = part.get("type", "")
                    sp = simplify_part(part)
                    if sp:
                        out = {"type": "part", "message_id": part.get("messageID"), "part": sp}
                elif t == "message.part.delta":
                    pid = pr.get("partID") or pr.get("id")
                    if part_kind.get(pid) in ("text", "reasoning"):
                        out = {"type": "delta", "part_id": pid, "kind": part_kind[pid],
                               "message_id": pr.get("messageID"), "text": pr.get("delta") or ""}
                elif t == "message.updated":
                    info = pr.get("info") or {}
                    out = {"type": "message", "id": info.get("id"), "role": info.get("role"),
                           "context_used": (info.get("tokens") or {}).get("input")}
                elif t == "permission.asked":
                    if auto:
                        async with oc.client() as c:
                            await c.post(f"/permission/{pr.get('id')}/reply", params={"directory": directory},
                                         json={"reply": "once"})
                        out = {"type": "notice", "text": f"Auto-approved: {pr.get('permission')}"}
                    else:
                        out = {"type": "permission", **simplify_permission(pr)}
                elif t == "permission.replied":
                    out = {"type": "permission_replied", "id": pr.get("requestID")}
                elif t == "session.status":
                    out = {"type": "status", "busy": (pr.get("status") or {}).get("type") != "idle"}
                elif t == "session.idle":
                    out = {"type": "idle"}
                elif t == "session.error":
                    err = pr.get("error") or {}
                    out = {"type": "error", "message": (err.get("data") or {}).get("message") or err.get("name") or "error"}
                if out:
                    yield f"data: {json.dumps(out, ensure_ascii=False)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- used by Running tasks / Kill all
async def busy_sessions() -> list[dict]:
    if not (oc.proc and oc.proc.poll() is None):
        return []
    out = []
    for row in db._q("SELECT * FROM agent_sessions ORDER BY updated DESC LIMIT 30"):
        try:
            if row["id"] in await _busy_map(row["directory"]):
                out.append({"id": row["id"], "title": row["title"], "directory": row["directory"]})
        except Exception:
            pass
    return out


async def abort_all() -> int:
    n = 0
    for s in await busy_sessions():
        try:
            async with oc.client() as c:
                await c.post(f"/session/{s['id']}/abort", params={"directory": s["directory"]})
            n += 1
        except Exception:
            pass
    return n
