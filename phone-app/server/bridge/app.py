"""FastAPI server: auth, sessions, streaming chat with tool calling, uploads, files, exec, memory."""
import asyncio
import base64
import io
import json
import os
import mimetypes
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from . import db, memory, tools
from . import privacy  # noqa: E402  (patches db first: vault encryption, temporary chats)
from . import ocr as ocr_mod
from .config import DATA_DIR, config, llm_api_base

app = FastAPI(title="LocalAI Bridge", docs_url=None, redoc_url=None, openapi_url=None)
memory.start()   # loads the embedding model in the background
state = {"public_url": None}
MAX_UPLOAD = 50 * 1024 * 1024

# ---------------------------------------------------------------- auth
_failures: dict[str, deque] = defaultdict(deque)


def client_ip(req: Request) -> str:
    return req.headers.get("cf-connecting-ip") or (req.client.host if req.client else "?")


def is_local_request(req: Request) -> bool:
    """True only for requests made on this PC itself (not arriving through the tunnel)."""
    tunneled = any(h in req.headers for h in ("cf-connecting-ip", "cf-ray", "x-forwarded-for"))
    host = (req.headers.get("host") or "").lower()
    host_ok = host.startswith(("127.0.0.1:", "localhost:", "[::1]:")) or host in ("127.0.0.1", "localhost", "[::1]")
    return not tunneled and host_ok and req.client is not None and req.client.host in ("127.0.0.1", "::1")


LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


@app.middleware("http")
async def host_guard(req: Request, call_next):
    """Block DNS-rebinding: a request that did not come through Cloudflare must address us as localhost.
    (A malicious web page could otherwise point its own domain at 127.0.0.1 and read /pair.)"""
    tunneled = "cf-ray" in req.headers or "cf-connecting-ip" in req.headers
    h = (req.headers.get("host") or "").lower()
    host = h.split("]")[0] + "]" if h.startswith("[") else h.rsplit(":", 1)[0]
    if not tunneled and host not in LOCAL_HOSTS:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Forbidden host", status_code=403)
    return await call_next(req)


async def require_auth(req: Request):
    # the wrong-key lock is for guesses through the tunnel; a program on this PC can read config.json anyway, so a local
    # app with an old key (after Change access key) only gets 401, and never locks itself out
    local = is_local_request(req)
    ip = client_ip(req)
    q = _failures[ip]
    now = time.time()
    while q and now - q[0] > 600:
        q.popleft()
    if not local and len(q) >= 10:
        raise HTTPException(429, "Too many failed attempts, try again later")
    auth = req.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not token or not secrets.compare_digest(token.encode(), config["auth_token"].encode()):
        if not local:
            q.append(now)
        raise HTTPException(401, "Invalid token")
    privacy.vault_key.set(privacy.key_from_header(req.headers.get("x-vault-key")))   # only while the phone unlocked it


Auth = Depends(require_auth)


# ---------------------------------------------------------------- LLM helpers
def llm_headers():
    k = config.data.get("llm_api_key", "")
    return {"Authorization": f"Bearer {k}"} if k else {}


async def list_models() -> list[str]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(llm_api_base() + "/models", headers=llm_headers())
        r.raise_for_status()
        return [m["id"] for m in r.json().get("data", [])]


async def pick_model(requested: str | None) -> str:
    if requested:
        return requested
    if config["default_model"]:
        return config["default_model"]
    models = await list_models()
    if not models:
        raise RuntimeError("The LLM server has no models loaded.")
    return models[0]


_ctx_cache = {"t": 0.0, "n": None}


_CTX_KEYS = ("max_model_len", "context_length", "max_context_length", "context_size", "n_ctx", "max_seq_len")


def _find_ctx(d) -> int | None:
    if isinstance(d, dict):
        for k in _CTX_KEYS:
            if isinstance(d.get(k), int) and d[k] > 0:
                return d[k]
        for v in d.values():
            if isinstance(v, (dict, list)) and (n := _find_ctx(v)):
                return n
    elif isinstance(d, list):
        for v in d:
            if n := _find_ctx(v):
                return n
    return None


async def context_size() -> int | None:
    """Model context window. Set "context_size" in config.json to force it; otherwise it is detected from
    /v1/models (vLLM, EXL3, LM Studio: max_model_len / context_length), llama.cpp /props,
    TabbyAPI /v1/model (max_seq_len) or /health."""
    if config.data.get("context_size"):
        return int(config["context_size"])
    if time.time() - _ctx_cache["t"] < (60 if _ctx_cache["n"] else 5):  # retry quickly after a failure
        return _ctx_cache["n"]
    n = None
    base = llm_api_base()
    root = base[:-3]  # strip /v1
    async with httpx.AsyncClient(timeout=4) as c:
        for url in (base + "/models", root + "/props", base + "/model", root + "/health"):
            try:
                r = await c.get(url, headers=llm_headers())
                if r.status_code == 200 and (n := _find_ctx(r.json())):
                    break
            except Exception:
                continue
    _ctx_cache.update(t=time.time(), n=n)
    return n


def image_data_uri(att: dict) -> str:
    raw = Path(att["path"]).read_bytes()
    try:  # downscale big phone photos to keep the context small
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        if max(im.size) > 1536 or len(raw) > 1_500_000:
            im.thumbnail((1536, 1536))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=85)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    return f"data:{att['mime']};base64," + base64.b64encode(raw).decode()


def system_prompt(message: str = "") -> str:
    """Kept the same for the whole day: llama.cpp reuses what it already read only while the start of the prompt does not
    change (hybrid models like MiniCPM-V 4.7 / Qwen3.6 even re-read EVERYTHING after any change). So no clock and no
    memories here; each user message carries its own sent-time and related memories instead (message_context)."""
    parts = [config["system_prompt"],
             f"Today's date: {time.strftime('%A %Y-%m-%d')} (each user message shows when it was sent)",
             f"Allowed folders: {', '.join(tools.allowed_roots())}",
             f"Code working directory: {config['workspace']}",
             "Working style: when a request needs a tool or more than one step, your FIRST tool call must be update_tasks "
             "with your plan (short steps), then keep it current: mark a step in_progress when you start it and done "
             "when it is finished, and add steps you discover. The user watches this list on their phone to see "
             "exactly what you are doing. When you need the user to decide something (an approach, a file, yes/no, "
             "one of several options), call ask_user instead of guessing or ending your reply with a question.",
             "Some user messages end with a [Context …] block from the app: when the message was sent and what you "
             "remember about the user that relates to it. Use it naturally; never mention the block."]
    from . import profile
    pb = profile.prompt_block()      # changes at most once a day: the prompt cache keeps working
    if pb:
        parts.append(pb)
    return "\n\n".join(parts)


# what a user message is sent with, fixed when it arrives (so earlier prompt text never changes)
db._conn.execute("CREATE TABLE IF NOT EXISTS message_context(message_id INTEGER PRIMARY KEY, text TEXT)")
db._conn.commit()


def attach_context(mid: int, content: str, voice: bool = False, translate: bool = False, drive: bool = False):
    """Sent-time + memories related to this message, stored once with the message."""
    parts = [f"sent {time.strftime('%Y-%m-%d %H:%M (%A)')}"]
    if drive and not translate:   # car mode: a spoken conversation only
        parts.append("CAR MODE: the user is driving and can only listen and speak. Just talk with them: never write code, "
                     "never offer numbered choices or options to pick from, never ask them to approve, confirm or choose "
                     "anything, and do not start tasks on the PC. If something needs the screen, say in one sentence that "
                     "it can be done later in the app")
        voice = True
    if translate:   # translate mode (driving): the message is to be translated, not answered
        parts.append("TRANSLATE MODE: do not answer or comment on the message. If it is in Arabic, reply with only its "
                     "natural English translation. If it is in English or another language, reply with only its Arabic "
                     "translation, written with tashkeel. Nothing else: no quotes, no notes")
        voice = False
    if voice:   # read aloud to the user (maybe while driving): spoken style, short
        parts.append("asked by voice and your reply is read aloud (the user may be driving): answer in a few short, "
                     "plain spoken sentences in the user's language; no tables, code, lists or links unless asked. When you answer "
                     "in Arabic, write it with full tashkeel (diacritics, e.g. مَرْحَبًا بِكَ) so the text-to-speech voice "
                     "pronounces every word correctly, and write numbers as digits")
    mem = memory.context(content, recent=False)
    if mem:
        parts.append(mem)
    db._q("INSERT OR REPLACE INTO message_context VALUES(?,?)", (mid, "\n".join(parts)))


def _contexts(rows) -> dict:
    ids = [r["id"] for r in rows if r["role"] == "user"]
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    return {r["message_id"]: r["text"] for r in db._q(f"SELECT * FROM message_context WHERE message_id IN ({q})", ids)}


def build_llm_messages(session_id: str) -> list[dict]:
    summ = db.get_summary(session_id)
    rows = db.get_messages(session_id)
    if summ:
        rows = [r for r in rows if r["id"] > summ["upto_id"]]
    # no sliding window: dropping the oldest messages would change the start of the prompt on every step and make the
    # model re-read the whole chat; long chats are shortened by compression (a summary) instead
    rows = rows[-1000:]
    while rows and rows[0]["role"] != "user":
        rows.pop(0)
    last_user_idx = max((i for i, r in enumerate(rows) if r["role"] == "user"), default=-1)
    ctx = _contexts(rows)
    sp = system_prompt()
    from . import projects
    pc = projects.context(session_id)
    if pc:   # a project chat: goal, notes and folder of the project
        sp += "\n\n" + pc
    if summ:
        sp += "\n\nSummary of the earlier part of this conversation (older messages were compressed):\n" + summ["summary"]
    out = [{"role": "system", "content": sp}]
    for i, r in enumerate(rows):
        if r["role"] == "user":
            text = r["content"] or ""
            if ctx.get(r["id"]):
                text += f"\n\n[Context from the app: {ctx[r['id']]}]"
            images = []
            for a in r["attachments"]:
                att = db.get_attachment(a["id"])
                if not att:
                    continue
                ocr = ocr_mod.ocr_text(att["id"])
                if ocr:   # read with the OCR sub-model: its text (tables, formulas, layout kept) goes to the chat model
                    text += f"\n\n[Attached file: {att['filename']} saved at {att['path']}, read with OCR]\n{ocr}"
                    if att["kind"] == "image" and i == last_user_idx:
                        images.append(att)
                    continue
                if att["kind"] == "image":
                    if i == last_user_idx:
                        images.append(att)
                        text += f"\n\n[image attached: {att['filename']} saved at {att['path']}]"
                    else:
                        text += f"\n\n[image attached earlier: {att['filename']} saved at {att['path']}]"
                elif att["text"] and re.sub(r"--- page \d+ ---", "", att["text"]).strip():
                    text += f"\n\n[Attached file: {att['filename']} saved at {att['path']}]\n{att['text']}"
                elif att["kind"] == "pdf":   # a scan: no text layer
                    text += (f"\n\n[Attached file: {att['filename']} saved at {att['path']}: a scanned PDF without a text "
                             f"layer; read it with ocr_document if that tool is available]")
                else:
                    text += f"\n\n[Attached file: {att['filename']} saved at {att['path']}]"
            if images:
                content = [{"type": "text", "text": text}] + [
                    {"type": "image_url", "image_url": {"url": image_data_uri(a)}} for a in images]
                out.append({"role": "user", "content": content})
            else:
                out.append({"role": "user", "content": text})
        elif r["role"] == "assistant":
            m = {"role": "assistant", "content": r["content"] or ""}
            if r["tool_calls"]:
                m["tool_calls"] = r["tool_calls"]
            out.append(m)
        elif r["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": r["tool_call_id"], "name": r["name"],
                        "content": r["content"]})
    return out


# ---------------------------------------------------------------- conversation compression
KEEP_USER_TURNS = 2  # the latest exchanges stay verbatim


def _strip_think(t: str) -> str:
    return re.sub(r"(?s)<think>.*?</think>", "", t or "").strip()


async def compress_session(sid: str, model: str, client: httpx.AsyncClient) -> dict | None:
    """Summarize everything except the last KEEP_USER_TURNS exchanges. Returns None if there is nothing to do."""
    summ = db.get_summary(sid)
    rows = db.get_messages(sid)
    if summ:
        rows = [r for r in rows if r["id"] > summ["upto_id"]]
    user_idx = [i for i, r in enumerate(rows) if r["role"] == "user"]
    if len(user_idx) <= KEEP_USER_TURNS:
        return None
    old = rows[:user_idx[-KEEP_USER_TURNS]]
    lines = []
    for r in old:
        text = (r["content"] or "")[: (1500 if r["role"] == "tool" else 4000)]
        if r["role"] == "assistant" and r["tool_calls"]:
            text += "\n[called tools: " + ", ".join(
                f"{t['function']['name']}({t['function']['arguments'][:300]})" for t in r["tool_calls"]) + "]"
        if r["attachments"]:
            text += "\n[attachments: " + ", ".join(a["filename"] for a in r["attachments"]) + "]"
        lines.append(f"### {r['role'].upper()}{' (' + r['name'] + ')' if r.get('name') else ''}\n{text}")
    transcript = "\n\n".join(lines)[-150_000:]
    prompt = ((f"Existing summary of even earlier messages:\n{summ['summary']}\n\n" if summ else "") +
              "Conversation to summarize:\n\n" + transcript + "\n\n"
              "Write a compact but complete summary of everything above, to replace it in the assistant's memory. "
              "Keep: the user's goals and preferences, decisions made, facts learned, file paths, commands, code "
              "snippets that still matter, results of tools, and any unfinished tasks. Use short bullet points.")
    r = await client.post(llm_api_base() + "/chat/completions", headers=llm_headers(), json={
        "model": model, "stream": False, "max_tokens": 2048, "temperature": 0.2,
        "messages": [{"role": "system", "content": "You compress chat histories into faithful summaries."},
                     {"role": "user", "content": prompt}]})
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    summary = _strip_think(msg.get("content") or "") or _strip_think(msg.get("reasoning_content") or "")
    if not summary:
        raise RuntimeError("The model returned an empty summary")
    db.set_summary(sid, summary, old[-1]["id"])
    st = db.get_stats(sid) or {}
    st.update(ctx_used=None)  # unknown until the next reply; prevents compressing again immediately
    db.set_stats(sid, st)
    return {"messages": len(old), "summary_chars": len(summary)}


async def compress_turn(run, model: str | None):
    """Manual 'Compress now' as a background run (works through Cloudflare's 100 s request limit)."""
    try:
        model = await pick_model(model)
        run.emit({"type": "phase", "phase": "compressing"})
        async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10)) as client:
            res = await compress_session(run.sid, model, client)
        run.emit({"type": "compressed", **res} if res else
                 {"type": "notice", "text": "Nothing to compress yet - the conversation is still short."})
        run.emit({"type": "done"})
    except asyncio.CancelledError:
        run.emit({"type": "error", "message": "Compression stopped."})
    except Exception as e:
        run.emit({"type": "error", "message": f"Compression failed: {type(e).__name__}: {e}"})
    finally:
        runs.pop(run.sid, None)
        for q in run.queues:
            q.put_nowait(None)


# ---------------------------------------------------------------- chat engine
# car mode: read-only tools that never ask the user anything
DRIVE_TOOLS = {"web_search", "fetch_url", "search_chats", "project_knowledge"}


class Run:
    """A chat turn running in the background; survives phone disconnects."""

    def __init__(self, sid, web=False, auto_approve=False, compress_at=0.0, email=False, organizer=False, thinking="auto", ocr="off", sandbox=False, pc=False, drive=False):
        self.sid = sid
        self.drive = bool(drive)   # car mode: only the DRIVE_TOOLS, nothing that needs the screen
        self.thinking = thinking
        self.ocr = ocr if ocr in ocr_mod.MODES else "off"
        self.sandbox = bool(sandbox)
        self.pc = bool(pc)
        self.compress_at = compress_at
        self.web = web
        self.email, self.organizer = email, organizer      # access switches from the phone (off = no such tools)
        self.auto_approve = auto_approve
        self.queues: list[asyncio.Queue] = []
        self.history: list[dict] = []
        self.stopped = False
        self.task: asyncio.Task | None = None
        # live state for the "Running tasks" screen
        self.started = time.time()
        self.phase, self.tool, self.tokens, self.tps = "starting", "", 0, None
        self.plan: list[dict] = []

    def emit(self, ev: dict):
        t = ev.get("type")
        if t == "phase":
            self.phase, self.tool = ev.get("phase", ""), ev.get("name", "")
        elif t == "progress":
            self.phase = ev.get("phase", self.phase)
            self.tokens = ev.get("tokens") or self.tokens
            self.tps = ev.get("tps") or self.tps
        elif t == "approval_required":
            self.phase, self.tool = "approval", ev.get("name", "")
        elif t == "tasks":
            self.plan = ev.get("tasks") or []
        elif t == "question_required":
            self.phase, self.tool = "question", "ask_user"
        self.history.append(ev)
        for q in self.queues:
            q.put_nowait(ev)


runs: dict[str, Run] = {}
approvals: dict[str, dict] = {}  # call_id -> {"future", "session_id", "name", "args"}
questions: dict[str, dict] = {}  # call_id -> {"future", "session_id", "question", "options", "multiple", "allow_other"}


def _question_view(k: str, v: dict) -> dict:
    return {"id": k, "question": v["question"], "options": v["options"], "multiple": v["multiple"],
            "allow_other": v["allow_other"]}


def normalize_tasks(raw) -> list[dict]:
    """The model's plan as [{title, status}], tolerant of strings and odd status names."""
    out = []
    for t in raw if isinstance(raw, list) else []:
        if isinstance(t, str):
            t = {"title": t}
        if not isinstance(t, dict) or not str(t.get("title", "")).strip():
            continue
        s = str(t.get("status", "pending")).lower().replace(" ", "_").replace("-", "_")
        s = "done" if s in ("done", "completed", "complete", "finished") else (
            "in_progress" if s in ("in_progress", "active", "running", "doing", "started") else "pending")
        out.append({"title": str(t["title"]).strip()[:120], "status": s})
    return out[:20]


def last_plan(sid: str) -> list[dict]:
    """The latest update_tasks plan of a session (kept in its message history, so it survives restarts)."""
    for r in reversed(db.get_messages(sid)):
        for tc in reversed(r.get("tool_calls") or []):
            if tc.get("function", {}).get("name") == "update_tasks":
                try:
                    return normalize_tasks(json.loads(tc["function"].get("arguments") or "{}").get("tasks"))
                except (json.JSONDecodeError, AttributeError):
                    return []
    return []


async def ask_user(run: "Run", call_id: str, args: dict) -> str:
    """The ask_user tool: show the choices on the phone and wait for the answer (the reply pauses meanwhile)."""
    opts = [str(o).strip() for o in (args.get("options") or []) if str(o).strip()][:8]
    q = {"future": asyncio.get_running_loop().create_future(), "session_id": run.sid,
         "question": str(args.get("question") or "Choose an option").strip(), "options": opts,
         "multiple": bool(args.get("multiple")), "allow_other": args.get("allow_other", True) is not False}
    questions[call_id] = q
    run.emit({"type": "question_required", **_question_view(call_id, q)})
    run.emit({"type": "phase", "phase": "question", "name": "ask_user"})
    try:
        answer = await asyncio.wait_for(q["future"], 3600)
    except asyncio.TimeoutError:
        answer = None
    finally:
        questions.pop(call_id, None)
    run.emit({"type": "question_answered", "id": call_id, "answer": answer or ""})
    if not answer:
        return "The user did not answer. Do not assume a choice: say that you are waiting for their answer."
    return f"The user answered: {answer}"


async def stream_completion(client, payload, run: Run):
    """Streams one completion; returns (content, reasoning, tool_calls, stats)."""
    content, reasoning, calls = "", "", {}
    usage, timings = {}, {}
    n_tok, t_first, t_last_progress = 0, None, 0.0
    t_start = time.time()
    url = llm_api_base() + "/chat/completions"
    if os.environ.get("BRIDGE_DUMP_PROMPTS"):      # debugging the prompt cache: keep each request as sent
        (DATA_DIR / "dumps").mkdir(exist_ok=True)
        (DATA_DIR / "dumps" / f"{int(time.time() * 1000)}.json").write_text(json.dumps(payload), encoding="utf-8")
    run.emit({"type": "phase", "phase": "prompt"})  # model is reading the conversation
    async with client.stream("POST", url, json=payload, headers=llm_headers()) as r:
        if r.status_code >= 400:
            body = (await r.aread()).decode(errors="replace")
            raise httpx.HTTPStatusError(body[:2000], request=r.request, response=r)
        async for line in r.aiter_lines():
            if run.stopped:
                break
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            usage = chunk.get("usage") or usage
            timings = chunk.get("timings") or timings
            if not chunk.get("choices"):
                continue
            d = chunk["choices"][0].get("delta") or {}
            if d.get("content") or d.get("reasoning_content") or d.get("reasoning") or d.get("tool_calls"):
                n_tok += 1
                now = time.time()
                if t_first is None:
                    t_first = now
                if now - t_last_progress >= 1.0:  # live progress once per second
                    t_last_progress = now
                    phase = "tool_args" if d.get("tool_calls") else ("writing" if d.get("content") else "thinking")
                    span = now - t_first
                    run.emit({"type": "progress", "phase": phase, "tokens": n_tok,
                              "tps": round(n_tok / span, 1) if span > 0.5 else None})
            rz = d.get("reasoning_content") or d.get("reasoning")
            if rz:
                reasoning += rz
                run.emit({"type": "reasoning", "text": rz})
            if d.get("content"):
                content += d["content"]
                run.emit({"type": "delta", "text": d["content"]})
            for tc in d.get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                slot["id"] = tc.get("id") or slot["id"]
                fn = tc.get("function") or {}
                slot["name"] += fn.get("name") or ""
                slot["args"] += fn.get("arguments") or ""
    tool_calls = [{"id": c["id"] or f"call_{uuid.uuid4().hex[:12]}", "type": "function",
                   "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                  for _, c in sorted(calls.items())]
    gen_time = (time.time() - t_first) if t_first else 0
    stats = {
        "prompt_tokens": usage.get("prompt_tokens") or timings.get("prompt_n"),
        "completion_tokens": usage.get("completion_tokens") or timings.get("predicted_n") or n_tok,
        "tps": round(timings["predicted_per_second"], 1) if timings.get("predicted_per_second")
        else (round((usage.get("completion_tokens") or n_tok) / gen_time, 1) if gen_time > 0.5 else None),
        "prompt_tps": round(timings["prompt_per_second"], 1) if timings.get("prompt_per_second") else None,
        "seconds": round(time.time() - t_start, 1),
    }
    return content, reasoning, tool_calls, stats


# Thinking effort chosen in the apps: off, or on with a token budget (llama.cpp ends the thinking at the budget and
# the model answers). Effort = how many tokens the model may think before it must act.
THINKING = {"off": 0, "low": 1024, "medium": 4096, "high": 16384, "max": -1}
THINK_STOP = "\n\nI have thought enough about this; now I will act or answer.\n"


def apply_thinking(payload: dict, mode: str):
    """Add llama.cpp's per-request thinking options; 'auto' leaves the model's default."""
    if mode not in THINKING:
        return
    budget = THINKING[mode]
    # enable_thinking: Qwen / MiniCPM style templates; reasoning_strength: Muse Glimmer (no "off" level, so off = low).
    # A template ignores the settings it does not use.
    payload["chat_template_kwargs"] = {"enable_thinking": budget != 0,
                                       "reasoning_strength": {"off": "low", "max": "xhigh"}.get(mode, mode)}
    if budget == 0:   # off: also ends reasoning at once for models with no thinking switch (e.g. Flint)
        payload["reasoning_budget_tokens"] = 0
        payload["reasoning_budget_message"] = ""
    if budget > 0:
        payload["reasoning_budget_tokens"] = budget
        payload["reasoning_budget_message"] = THINK_STOP
    if budget != 0 and payload.get("max_tokens"):   # room for the thinking AND the answer
        payload["max_tokens"] += budget if budget > 0 else 32768


async def chat_turn(run: Run, model: str | None):
    sid = run.sid
    tools.current_session.set(sid)
    tools.current_sandbox.set(run.sandbox)
    try:
        if run.ocr != "off":   # OCR on: read the attached images / PDFs first, whatever the chat model would do
            last_user = next((m for m in reversed(db.get_messages(sid)) if m["role"] == "user"), None)
            ids = [a["id"] for a in (last_user or {}).get("attachments") or []]
            if ids:
                run.emit({"type": "phase", "phase": "tool", "name": "ocr_document"})
                await ocr_mod.auto_ocr(run.ocr, ids, lambda m: run.emit({"type": "notice", "text": m}),
                                       stopped=lambda: run.stopped)
                if run.stopped:
                    run.emit({"type": "done"})
                    return
        model = await pick_model(model)
        use_tools = True
        use_usage = True
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10)) as client:
            for _round in range(config["max_tool_rounds"]):
                st = db.get_stats(sid) or {}
                if run.compress_at and st.get("ctx_used") and st.get("ctx_size") \
                        and st["ctx_used"] / st["ctx_size"] >= run.compress_at:
                    run.emit({"type": "phase", "phase": "compressing"})
                    try:
                        res = await compress_session(sid, model, client)
                        if res:
                            run.emit({"type": "compressed", **res})
                    except Exception as e:
                        run.emit({"type": "notice", "text": f"Auto-compress failed: {e}"})
                payload = {"model": model, "messages": build_llm_messages(sid), "stream": True}
                if use_usage:
                    payload["stream_options"] = {"include_usage": True}
                if config.data.get("max_tokens"):
                    payload["max_tokens"] = int(config["max_tokens"])
                apply_thinking(payload, run.thinking)
                if use_tools:
                    payload["tools"] = tools.tool_schemas(web=run.web, email=run.email, organizer_access=run.organizer)
                    from . import projects, pc_tools
                    if run.pc:
                        payload["tools"] += pc_tools.schemas()
                    if projects.of_session(sid):
                        payload["tools"].append(projects.note_tool_schema())
                        payload["tools"].append(projects.knowledge_tool_schema())
                    if run.ocr != "off":
                        payload["tools"].append(ocr_mod.schema())
                    from . import imagegen
                    if imagegen.ready():
                        payload["tools"].append(imagegen.schema())
                    if run.drive:
                        payload["tools"] = [s for s in payload["tools"] if s["function"]["name"] in DRIVE_TOOLS]
                        if not payload["tools"]:
                            del payload["tools"]
                try:
                    content, reasoning, tool_calls, stats = await stream_completion(client, payload, run)
                except httpx.HTTPStatusError as e:
                    if use_usage and "stream_options" in str(e):
                        use_usage = False
                        continue
                    if use_tools and "tool" in str(e).lower():
                        use_tools = False
                        run.emit({"type": "notice", "text": "Model does not support tools; continuing without them."})
                        continue
                    raise
                db.add_message(sid, "assistant", content, reasoning=reasoning or None,
                               tool_calls=tool_calls or None)
                ctx = await context_size()
                used = (stats["prompt_tokens"] or 0) + (stats["completion_tokens"] or 0)
                stats.update(ctx_used=used or None, ctx_size=ctx)
                db.set_stats(sid, stats)
                run.emit({"type": "stats", **stats})
                if not tool_calls or run.stopped:
                    break
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    run.emit({"type": "tool_call", "id": tc["id"], "name": name, "args": args})
                    from . import pc_tools
                    blocked = ((name in tools.EMAIL_TOOLS and not run.email)
                               or (name in tools.ORGANIZER_TOOLS and not run.organizer)
                               or (name in pc_tools.TOOL_NAMES and not run.pc)
                               or (name == "save_memory" and privacy.is_private(sid))
                               or (run.drive and name not in DRIVE_TOOLS))
                    approval = "auto" if name in tools.NEEDS_APPROVAL else "not needed"
                    if blocked:
                        approval = "blocked"   # the model asked for a tool the user did not switch on: refuse, never run it
                        what = ("email" if name in tools.EMAIL_TOOLS else "PC actions" if name in pc_tools.TOOL_NAMES
                                else "memory (this is a private / temporary chat)" if name == "save_memory"
                                else "tasks, notes and calendar")
                        result, atts = (f"Access denied: the user has not allowed {what} access in this chat. Tell them to "
                                        f"switch on '{what}' access in the app (paperclip menu) if they want you to use it."), []
                        if run.drive and name not in DRIVE_TOOLS:
                            result = ("Not available: the user is driving (car mode). Do not use tools, do not offer "
                                      "choices; just answer by talking, in a few short sentences.")
                    elif name == "ask_user":
                        result, atts = await ask_user(run, tc["id"], args), []
                    elif name == "generate_image":
                        from . import imagegen
                        run.emit({"type": "phase", "phase": "tool", "name": name})
                        result, atts = await imagegen.generate(args, lambda m: run.emit({"type": "notice", "text": m}),
                                                               lambda: run.stopped)
                    elif name == "ocr_document":
                        run.emit({"type": "phase", "phase": "tool", "name": name})
                        result, atts = await ocr_mod.run(run.ocr, args,
                                                         lambda m: run.emit({"type": "notice", "text": m})), []
                    elif name == "project_note":
                        from . import projects
                        result, atts = projects.add_note(sid, str(args.get("text", ""))), []
                    elif name == "project_knowledge":
                        from . import projects
                        result, atts = await asyncio.to_thread(projects.knowledge_tool, sid, args), []
                    elif name == "update_tasks":
                        plan = normalize_tasks(args.get("tasks"))
                        run.emit({"type": "tasks", "tasks": plan})
                        done = sum(t["status"] == "done" for t in plan)
                        result, atts = f"Task list updated ({done}/{len(plan)} done). Continue with the work.", []
                    elif name in tools.ALWAYS_APPROVE or (name in tools.NEEDS_APPROVAL and config["require_tool_approval"]
                                                          and not run.auto_approve
                                                          and not (name == "run_code" and run.sandbox)):  # sandboxed: safe
                        fut = asyncio.get_running_loop().create_future()
                        approvals[tc["id"]] = {"future": fut, "session_id": sid, "name": name, "args": args}
                        run.emit({"type": "approval_required", "id": tc["id"], "name": name, "args": args})
                        run.emit({"type": "phase", "phase": "approval", "name": name})
                        try:
                            ok = await asyncio.wait_for(fut, 3600)
                        except asyncio.TimeoutError:
                            ok = False
                        finally:
                            approvals.pop(tc["id"], None)
                        approval = "approved" if ok else "denied"
                        if not ok:
                            result, atts = "The user denied this action.", []
                        else:
                            run.emit({"type": "phase", "phase": "tool", "name": name})
                            result, atts = await asyncio.to_thread(tools.execute_tool, name, args)
                    else:
                        run.emit({"type": "phase", "phase": "tool", "name": name})
                        result, atts = await asyncio.to_thread(tools.execute_tool, name, args)
                    db.add_message(sid, "tool", result, attachments=atts or None, tool_call_id=tc["id"], name=name)
                    audit.log(sid, name, args, approval, result, "schedule" if getattr(run, "scheduled", False) else "chat")
                    run.emit({"type": "tool_result", "id": tc["id"], "name": name, "output": result,
                              "attachments": atts})
                    if run.stopped:
                        break
            else:
                run.emit({"type": "notice", "text": "Stopped: too many tool rounds."})
        sess = db.get_session(sid)
        if sess and sess["title"] == "New chat":
            first = next((m["content"] for m in db.get_messages(sid) if m["role"] == "user"), "")
            title = re.sub(r"\s+", " ", first).strip()[:48] or "Chat"
            db.update_session(sid, title=title)
            run.emit({"type": "title", "title": title})
        run.emit({"type": "done"})
        if not run.stopped and not privacy.is_private(sid):   # remember lasting facts (never from temp / vault chats)
            msgs = db.get_messages(sid)
            u = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
            a = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant" and m["content"]), "")
            asyncio.create_task(memory.review_turn(u or "", a or ""))
    except asyncio.CancelledError:
        run.emit({"type": "error", "message": "Stopped from the Running tasks screen."})
    except Exception as e:
        run.emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
    finally:
        runs.pop(sid, None)
        for q in run.queues:
            q.put_nowait(None)


def compact_history(history: list[dict]) -> list[dict]:
    """What a re-attaching app needs to catch up, in a few events: consecutive text / thinking chunks merged into one,
    only the latest progress kept. A 900-token reply replays as ~5 events instead of ~900, so the phone shows the reply
    so far at once instead of re-typing it from the start."""
    out: list[dict] = []
    last_progress = last_phase = None
    for ev in history:
        t = ev.get("type")
        if t == "progress":
            last_progress = ev
            continue
        if t == "phase":       # only the current phase matters (else "Reading the conversation" flashes again)
            last_phase = ev
            continue
        if t in ("delta", "reasoning") and out and out[-1].get("type") == t:
            out[-1] = {**out[-1], "text": out[-1].get("text", "") + ev.get("text", "")}
            continue
        out.append(dict(ev))
    if not any(e.get("type") in ("done", "error") for e in out[-1:]):
        out += [e for e in (last_phase, last_progress) if e]
    return out


def sse_response(run: Run, replay=False):
    q: asyncio.Queue = asyncio.Queue()
    if replay:
        for ev in compact_history(run.history):
            q.put_nowait(ev)
    run.queues.append(q)

    async def gen():
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    yield 'data: {"type": "ping"}\n\n'  # keeps Cloudflare open + tells the app we're alive
                    continue
                if ev is None:
                    break
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            if q in run.queues:
                run.queues.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- routes: misc
@app.get("/api/health")
async def health():
    return {"ok": True, "name": "LocalAI Bridge"}


@app.get("/api/info", dependencies=[Auth])
async def info():
    try:
        models, llm_ok = await list_models(), True
    except Exception as e:
        models, llm_ok = [], False
    return {"llm_base_url": llm_api_base(), "llm_ok": llm_ok, "models": models,
            "default_model": config["default_model"] or (models[0] if models else ""),
            "allowed_roots": tools.allowed_roots(), "workspace": config["workspace"],
            "code_exec": config["enable_code_exec"], "require_approval": config["require_tool_approval"]}


class TranslateIn(BaseModel):
    text: str
    to: str = "en"          # en | ar


@app.post("/api/translate", dependencies=[Auth])
async def translate(body: TranslateIn):
    """The Translator screen: one direct call to the loaded model, no chat history. Arabic output gets tashkeel so the
    phone's voice reads it correctly."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "nothing to translate")
    target = "Arabic (Modern Standard Arabic, written with tashkeel/diacritics)" if body.to == "ar" else "English"
    model = await pick_model(None)
    payload = {"model": model, "stream": False, "max_tokens": 1024, "temperature": 0.2,
               "chat_template_kwargs": {"enable_thinking": False, "reasoning_strength": "low"},
               "messages": [{"role": "system", "content": f"You are a translator. Translate the user's text into {target}. "
                             "Reply with only the translation: no quotes, notes, explanations or transliteration."},
                            {"role": "user", "content": text}]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as c:
        r = await c.post(llm_api_base() + "/chat/completions", headers=llm_headers(), json=payload)
        r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    out = _strip_think(msg.get("content") or "").strip().strip('"“”')
    return {"text": out, "to": body.to}


@app.post("/api/token/rotate", dependencies=[Auth])
async def token_rotate():
    """Change the access key from the phone: the old key stops working at once (other paired devices must re-pair).
    With a named tunnel the address stays the same, so this is how to lock out a lost phone or a leaked QR."""
    return {"token": config.regenerate_token()}


@app.get("/pair", response_class=HTMLResponse)
async def pair_page(req: Request):
    if not is_local_request(req):
        raise HTTPException(404)
    import qrcode
    import qrcode.image.svg
    url = state["public_url"] or f"http://127.0.0.1:{config['port']}"
    payload = json.dumps({"url": url, "token": config["auth_token"]})
    svg = qrcode.make(payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=12).to_string().decode()
    return f"""<!doctype html><meta charset=utf-8><title>Pair phone</title>
<body style="font-family:Segoe UI;text-align:center;padding:30px">
<h2>Scan with the LocalAI Bridge app</h2>{svg}<p><b>{url}</b></p>
<p style="color:#a00">Keep this QR private - it grants full access to this PC.</p>
<h3>LocalAI Bridge Desktop (another laptop)</h3>
<p>Copy this pairing code and paste it in the desktop app's connect screen:</p>
<textarea id=c readonly rows=3 style="width:90%;max-width:640px;font-family:Consolas">{html.escape(payload)}</textarea><br>
<button onclick="navigator.clipboard.writeText(document.getElementById('c').value);this.textContent='Copied'">Copy pairing code</button>
</body>"""


# ---------------------------------------------------------------- routes: sessions & chat
class NewSession(BaseModel):
    title: str = "New chat"
    model: str = ""


class PatchSession(BaseModel):
    title: str | None = None
    model: str | None = None


class ChatIn(BaseModel):
    content: str = ""
    attachments: list[str] = []
    model: str | None = None
    web: bool = False            # give the model web_search / fetch_url
    email: bool = False          # allow the Gmail tools (read / draft / send with approval)
    organizer: bool = False      # allow tasks, notes and calendar tools
    auto_approve: bool = False   # run code / write files without asking the phone
    compress_at: float = 0.0     # e.g. 0.75 = summarize old messages when 75% of the context is used; 0 = off
    thinking: str = "auto"       # auto (model default) | off | low | medium | high | max  (see THINKING)
    ocr: str = "off"             # OCR sub-model (Unlimited-OCR): off | gpu (swap with the chat model) | cpu
    sandbox: bool = False        # run_code in a Windows AppContainer: no network, no access to the user's files
    voice: bool = False          # asked by voice (mic / driving mode): the reply is read aloud, so keep it short
    translate: bool = False      # translate mode: translate the message (Arabic <-> English) instead of answering it
    pc: bool = False             # PC actions: look at the screen, open, move files, run saved scripts (approved)
    drive: bool = False          # car mode: talk only - no code, no approvals, no questions with choices


class ApprovalIn(BaseModel):
    approve: bool


@app.get("/api/sessions", dependencies=[Auth])
async def sessions_list():
    return [dict(s, running=s["id"] in runs, stats=db.get_stats(s["id"]))
            for s in db.list_sessions()]


@app.post("/api/sessions", dependencies=[Auth])
async def sessions_create(body: NewSession):
    return db.create_session(body.title, body.model)


@app.get("/api/sessions/{sid}", dependencies=[Auth])
async def sessions_get(sid: str):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404)
    pending = [{"id": k, "name": v["name"], "args": v["args"]}
               for k, v in approvals.items() if v["session_id"] == sid]
    summ = db.get_summary(sid)
    return {**s, "stats": db.get_stats(sid), "summary_upto": summ["upto_id"] if summ else None,
            "running": sid in runs, "messages": db.get_messages(sid), "pending_approvals": pending,
            "pending_questions": [_question_view(k, v) for k, v in questions.items() if v["session_id"] == sid],
            "plan": last_plan(sid)}


@app.patch("/api/sessions/{sid}", dependencies=[Auth])
async def sessions_patch(sid: str, body: PatchSession):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    return db.update_session(sid, **fields)


@app.delete("/api/sessions/{sid}", dependencies=[Auth])
async def sessions_delete(sid: str):
    if sid in runs:
        runs[sid].stopped = True
    db.delete_session(sid)
    return {"ok": True}


@app.post("/api/sessions/{sid}/chat", dependencies=[Auth])
async def chat(sid: str, body: ChatIn):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404)
    if sid in runs:
        raise HTTPException(409, "A reply is already running in this session")
    atts = []
    for aid in body.attachments:
        a = db.get_attachment(aid)
        if a:
            atts.append({"id": a["id"], "filename": a["filename"], "kind": a["kind"], "mime": a["mime"]})
    mid = db.add_message(sid, "user", body.content, attachments=atts or None)
    try:
        await asyncio.to_thread(attach_context, mid, body.content, body.voice, body.translate, body.drive)
    except Exception:
        pass   # memory is optional: the chat goes on without it
    if s["title"] == "New chat":  # name the chat right away, not after the reply
        first = re.sub(r"\s+", " ", body.content).strip() or (atts[0]["filename"] if atts else "")
        db.update_session(sid, title=first[:48] or "Chat")
    model = body.model or s["model"] or None
    if body.model and body.model != s["model"]:
        db.update_session(sid, model=body.model)
    run = Run(sid, web=body.web, auto_approve=body.auto_approve, compress_at=max(0.0, min(body.compress_at, 0.98)),
              email=body.email, organizer=body.organizer,
              thinking=body.thinking if body.thinking in THINKING or body.thinking == "auto" else "auto",
              ocr=body.ocr, sandbox=body.sandbox, pc=body.pc and not body.drive, drive=body.drive)
    runs[sid] = run
    resp = sse_response(run)
    run.task = asyncio.create_task(chat_turn(run, model))
    return resp


@app.post("/api/sessions/{sid}/compress", dependencies=[Auth])
async def compress(sid: str):
    s = db.get_session(sid)
    if not s:
        raise HTTPException(404)
    if sid in runs:
        raise HTTPException(409, "A reply is already running in this session")
    run = Run(sid)
    runs[sid] = run
    resp = sse_response(run)
    run.task = asyncio.create_task(compress_turn(run, s["model"] or None))
    return resp


@app.get("/api/sessions/{sid}/stream", dependencies=[Auth])
async def chat_resume(sid: str):
    """Re-attach to a reply that is still running (e.g. after the app was backgrounded)."""
    if sid not in runs:
        raise HTTPException(404, "Nothing running")
    return sse_response(runs[sid], replay=True)


class TruncateIn(BaseModel):
    message_id: int


@app.post("/api/sessions/{sid}/truncate", dependencies=[Auth])
async def sessions_truncate(sid: str, body: TruncateIn):
    """Remove a message and everything after it - used to edit a message and re-run the chat."""
    if sid in runs:
        raise HTTPException(409, "A reply is still running in this session")
    db.truncate_session(sid, body.message_id)
    return {"ok": True}


@app.post("/api/screenshot", dependencies=[Auth])
async def screenshot():
    """Capture the PC screen; returns an attachment the phone can show or send to the model."""
    return await asyncio.to_thread(tools.take_screenshot)


@app.post("/api/sessions/{sid}/stop", dependencies=[Auth])
async def chat_stop(sid: str):
    tools.kill_procs(session=sid)
    if sid in runs:
        runs[sid].stopped = True
        for k, v in list(approvals.items()):
            if v["session_id"] == sid and not v["future"].done():
                v["future"].set_result(False)
        for v in list(questions.values()):
            if v["session_id"] == sid and not v["future"].done():
                v["future"].set_result(None)
    return {"ok": True}


async def llm_busy() -> bool | None:
    """Is the LLM server generating right now (possibly for something we don't track)? None = unknown."""
    base = llm_api_base()
    root = base[:-3]
    async with httpx.AsyncClient(timeout=3) as c:
        try:
            r = await c.get(root + "/slots", headers=llm_headers())  # llama.cpp
            if r.status_code == 200 and isinstance(r.json(), list):
                return any(s.get("is_processing") for s in r.json())
        except Exception:
            pass
        try:
            d = (await c.get(root + "/health", headers=llm_headers())).json()  # EXL3 server and others
            if isinstance(d, dict) and "busy" in d:
                return bool(d["busy"])
        except Exception:
            pass
    return None


async def llm_abort() -> int | None:
    """Ask the LLM server to cancel everything it is generating (EXL3 serve_openai /v1/abort).
    Returns how many generations were cancelled, or None if the server has no abort endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(llm_api_base() + "/abort", headers=llm_headers())
        return r.json().get("cancelled", 0) if r.status_code == 200 else None
    except Exception:
        return None


@app.post("/api/llm/abort", dependencies=[Auth])
async def llm_abort_endpoint():
    n = await llm_abort()
    if n is None:
        raise HTTPException(501, "This LLM server can't cancel generations (no /v1/abort endpoint)")
    return {"cancelled": n}


@app.get("/api/tasks", dependencies=[Auth])
async def tasks_list():
    now = time.time()
    out = []
    for sid, r in list(runs.items()):
        s = db.get_session(sid)
        out.append({"session_id": sid, "title": s["title"] if s else "?", "phase": r.phase, "tool": r.tool,
                    "tokens": r.tokens, "tps": r.tps, "elapsed": round(now - r.started),
                    "waiting_approval": any(v["session_id"] == sid for v in approvals.values()),
                    "waiting_question": any(v["session_id"] == sid for v in questions.values()),
                    "step": next((p["title"] for p in r.plan if p["status"] == "in_progress"), ""),
                    "steps_done": sum(p["status"] == "done" for p in r.plan), "steps": len(r.plan)})
    return {"runs": out, "processes": tools.list_procs(), "llm_busy": await llm_busy(),
            "agents": await agent.busy_sessions()}


def _hard_stop(sid: str):
    r = runs.get(sid)
    tools.kill_procs(session=sid)
    for v in list(approvals.values()):
        if v["session_id"] == sid and not v["future"].done():
            v["future"].set_result(False)
    for v in list(questions.values()):
        if v["session_id"] == sid and not v["future"].done():
            v["future"].set_result(None)
    if r:
        r.stopped = True
        if r.task and not r.task.done():
            r.task.cancel()  # closes the LLM stream, which makes the LLM server stop generating


@app.post("/api/tasks/{sid}/stop", dependencies=[Auth])
async def task_stop(sid: str):
    _hard_stop(sid)
    return {"ok": True}


@app.post("/api/processes/{pid}/kill", dependencies=[Auth])
async def process_kill(pid: int):
    return {"killed": tools.kill_procs(pid=pid)}


@app.post("/api/tasks/kill_all", dependencies=[Auth])
async def tasks_kill_all():
    """Emergency stop: every running chat, every code process, every pending approval."""
    n_runs = len(runs)
    for sid in list(runs):
        _hard_stop(sid)
    n_procs = tools.kill_procs()
    n_agents = await agent.abort_all()
    llm = await llm_abort()  # also stops generations nobody is waiting for (orphans)
    return {"runs": n_runs, "processes": n_procs, "agents": n_agents, "llm_cancelled": llm}


@app.post("/api/approvals/{call_id}", dependencies=[Auth])
async def approve(call_id: str, body: ApprovalIn):
    a = approvals.get(call_id)
    if not a:
        raise HTTPException(404, "No pending approval")
    if not a["future"].done():
        a["future"].set_result(body.approve)
    return {"ok": True}


class AutoApproveIn(BaseModel):
    on: bool


@app.post("/api/sessions/{sid}/auto_approve", dependencies=[Auth])
async def session_auto_approve(sid: str, body: AutoApproveIn):
    """Auto-approve switched on or off while a reply is running: applies to the rest of this reply, and on also
    approves what is waiting now. Actions that always ask (PC actions, sending email...) still wait for the user."""
    run = runs.get(sid)
    if not run:
        return {"ok": True, "running": False, "approved": 0}
    run.auto_approve = body.on and not getattr(run, "drive", False)
    approved = 0
    if run.auto_approve:
        for a in list(approvals.values()):
            if a["session_id"] == sid and a["name"] not in tools.ALWAYS_APPROVE and not a["future"].done():
                a["future"].set_result(True)
                approved += 1
    return {"ok": True, "running": True, "approved": approved}


class AnswerIn(BaseModel):
    answer: str


@app.post("/api/questions/{call_id}", dependencies=[Auth])
async def answer_question(call_id: str, body: AnswerIn):
    """The user's choice for an ask_user question; the paused reply continues with it."""
    q = questions.get(call_id)
    if not q:
        raise HTTPException(404, "No pending question")
    if not q["future"].done():
        q["future"].set_result(body.answer.strip())
    return {"ok": True}


# ---------------------------------------------------------------- routes: uploads
def _safe_name(name: str) -> str:
    return re.sub(r"[^\w.\- ]", "_", Path(name or "file").name)[:120]


async def _save_upload(f: UploadFile, dest: Path) -> int:
    size = 0
    with dest.open("wb") as out:
        while chunk := await f.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File too large (50 MB max)")
            out.write(chunk)
    return size


@app.post("/api/uploads", dependencies=[Auth])
async def upload(file: UploadFile = File(...)):
    name = _safe_name(file.filename)
    dest = DATA_DIR / "uploads" / f"{uuid.uuid4().hex[:8]}_{name}"
    size = await _save_upload(file, dest)
    mime = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    ext = dest.suffix.lower()
    text, kind = None, "file"
    if mime == "application/pdf" or ext == ".pdf":
        kind, mime = "pdf", "application/pdf"
        try:
            text = await asyncio.to_thread(tools.extract_pdf_text, dest)
        except Exception as e:
            text = f"[could not extract PDF text: {e}]"
    elif mime.startswith("image/"):
        kind = "image"
    elif mime.startswith("text/") or ext in tools.TEXT_EXT:
        kind = "text"
        text = tools.truncate(dest.read_text(encoding="utf-8", errors="replace"), 60_000)
    a = db.add_attachment(name, mime, kind, str(dest), text, size)
    return {k: a[k] for k in ("id", "filename", "mime", "kind", "size")}


@app.get("/api/uploads/{aid}", dependencies=[Auth])
async def upload_get(aid: str):
    a = db.get_attachment(aid)
    if not a:
        raise HTTPException(404)
    return FileResponse(a["path"], media_type=a["mime"], filename=a["filename"])


# ---------------------------------------------------------------- routes: filesystem
@app.get("/api/fs/roots", dependencies=[Auth])
async def fs_roots():
    return {"roots": tools.allowed_roots(), "workspace": config["workspace"]}


class MkdirIn(BaseModel):
    parent: str
    name: str


class RenameIn(BaseModel):
    path: str
    new_name: str


@app.post("/api/fs/mkdir", dependencies=[Auth])
async def fs_mkdir(body: MkdirIn):
    try:
        parent = tools.resolve_path(body.parent)
        new = tools.resolve_path(str(parent / tools.safe_name(body.name)))
    except tools.ToolError as e:
        raise HTTPException(403, str(e))
    if not parent.is_dir():
        raise HTTPException(400, "Parent is not a folder")
    if new.exists():
        raise HTTPException(409, "Something with that name already exists")
    new.mkdir()
    return {"path": str(new)}


@app.post("/api/fs/rename", dependencies=[Auth])
async def fs_rename(body: RenameIn):
    try:
        src = tools.resolve_path(body.path)
        if any(src == Path(r).resolve() for r in tools.allowed_roots()):
            raise tools.ToolError("Can't rename a top-level allowed folder or drive")
        dst = tools.resolve_path(str(src.parent / tools.safe_name(body.new_name)))
    except tools.ToolError as e:
        raise HTTPException(403, str(e))
    if not src.exists():
        raise HTTPException(404, "Not found")
    if dst.exists():
        raise HTTPException(409, "Something with that name already exists")
    src.rename(dst)
    return {"path": str(dst)}


@app.get("/api/fs/list", dependencies=[Auth])
async def fs_list(path: str):
    try:
        return await asyncio.to_thread(tools.list_dir, path)
    except tools.ToolError as e:
        raise HTTPException(403, str(e))


@app.get("/api/fs/download", dependencies=[Auth])
async def fs_download(path: str):
    try:
        p = tools.resolve_path(path)
    except tools.ToolError as e:
        raise HTTPException(403, str(e))
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, filename=p.name)


@app.post("/api/fs/upload", dependencies=[Auth])
async def fs_upload(dir: str, file: UploadFile = File(...)):
    try:
        d = tools.resolve_path(dir)
    except tools.ToolError as e:
        raise HTTPException(403, str(e))
    if not d.is_dir():
        raise HTTPException(400, "Not a directory")
    dest = d / _safe_name(file.filename)
    size = await _save_upload(file, dest)
    return {"path": str(dest), "size": size}


# ---------------------------------------------------------------- routes: exec & memory
class ExecIn(BaseModel):
    language: str = "python"
    code: str


@app.post("/api/exec", dependencies=[Auth])
async def exec_code(body: ExecIn):
    try:
        return await asyncio.to_thread(tools.run_code, body.language, body.code)
    except tools.ToolError as e:
        raise HTTPException(400, str(e))


class MemoryIn(BaseModel):
    content: str
    category: str = "other"


class MemorySettings(BaseModel):
    auto_memory: bool


@app.get("/api/memory", dependencies=[Auth])
async def memory_list(q: str = "", category: str = ""):
    return await asyncio.to_thread(memory.list_all, q, category)


@app.get("/api/memory/status", dependencies=[Auth])
async def memory_status():
    return memory.status()


@app.post("/api/memory/settings", dependencies=[Auth])
async def memory_settings(b: MemorySettings):
    config["auto_memory"] = b.auto_memory
    return memory.status()


@app.post("/api/memory", dependencies=[Auth])
async def memory_add(body: MemoryIn):
    try:
        return await asyncio.to_thread(memory.add, body.content, body.category, "manual")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/api/memory/{mid}", dependencies=[Auth])
async def memory_edit(mid: int, body: MemoryIn):
    try:
        return await asyncio.to_thread(memory.update, mid, body.content, body.category)
    except KeyError as e:
        raise HTTPException(404, str(e))


# ---------------------------------------------------------------- OpenCode coding agent (beta feature)
from . import agent  # noqa: E402

app.include_router(agent.router, dependencies=[Auth])

# ---------------------------------------------------------------- V100-LLM model control (load / unload / status)
from . import models_ctl  # noqa: E402

app.include_router(models_ctl.router, dependencies=[Auth])
from . import bench  # noqa: E402

app.include_router(bench.router, dependencies=[Auth])
from . import tts  # noqa: E402

app.include_router(tts.router, dependencies=[Auth])
from . import projects  # noqa: E402

app.include_router(projects.router, dependencies=[Auth])
from . import notes  # noqa: E402

app.include_router(notes.router, dependencies=[Auth])
from . import research  # noqa: E402

app.include_router(research.router, dependencies=[Auth])
app.include_router(privacy.router, dependencies=[Auth])
from . import profile  # noqa: E402

app.include_router(profile.router, dependencies=[Auth])
from . import live  # noqa: E402

app.include_router(live.router, dependencies=[Auth])
from . import tutor  # noqa: E402

app.include_router(tutor.router, dependencies=[Auth])
from . import audit  # noqa: E402

app.include_router(audit.router, dependencies=[Auth])
from . import schedules  # noqa: E402

app.include_router(schedules.router, dependencies=[Auth])


@app.on_event("startup")
async def _start_background():
    asyncio.create_task(schedules.loop())   # scheduled prompts + temperature alerts

# ---------------------------------------------------------------- OpenAI-compatible API for the loaded model
from . import openai_proxy  # noqa: E402

app.include_router(openai_proxy.router)                          # protected by its own API key
app.include_router(openai_proxy.manage, dependencies=[Auth])     # key management: phone app only


@app.delete("/api/memory/{mid}", dependencies=[Auth])
async def memory_delete(mid: int):
    memory.delete(mid)
    return {"ok": True}


# ---------------------------------------------------------------- notes, tasks, calendar (+ Google) for the app and the model
from . import organizer  # noqa: E402

app.include_router(organizer.router, dependencies=[Auth])

from . import google_api  # noqa: E402

app.include_router(google_api.router, dependencies=[Auth])   # Google setup + mail list for the app
app.include_router(google_api.public)                         # OAuth redirect (PC browser, localhost only)
from . import email_tasks  # noqa: E402

app.include_router(email_tasks.router, dependencies=[Auth])   # tasks suggested from email (user accepts / dismisses)
