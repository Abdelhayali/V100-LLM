"""Live meeting assistant: the phone sends the meeting in 20-second pieces while it records; the PC transcribes each piece
(faster-whisper kept loaded on the CPU by ocr/stt_server.py, so the chat model stays on the GPU), the phone shows the
live transcript, and you can ask about the meeting while it runs. Stop -> summary, decisions and action items.
"""
import asyncio
import os
import subprocess
import time
import uuid

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()
PORT = 8782
URL = f"http://127.0.0.1:{PORT}"
meetings: dict[str, dict] = {}
_start_lock = asyncio.Lock()


async def _ensure_stt():
    async with _start_lock:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                if (await c.get(URL + "/health")).status_code == 200:
                    return
        except Exception:
            pass
        from . import ocr
        d = ocr.ocr_dir()
        if not (d / "stt_server.py").exists() or not (d / "whisper").exists():
            raise HTTPException(503, "speech-to-text is not installed (ocr/setup-ocr.bat)")
        subprocess.Popen([str(d / ".venv" / "Scripts" / "python.exe"), str(d / "stt_server.py"), "--port", str(PORT)],
                         cwd=str(d), env=dict(os.environ, PYTHONIOENCODING="utf-8", HF_HUB_OFFLINE="1"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        t0 = time.time()
        while time.time() - t0 < 180:
            await asyncio.sleep(1.5)
            try:
                async with httpx.AsyncClient(timeout=2) as c:
                    if (await c.get(URL + "/health")).status_code == 200:
                        return
            except Exception:
                pass
        raise HTTPException(503, "the speech-to-text server did not start")


async def _worker(mid: str):
    m = meetings[mid]
    while True:
        item = await m["queue"].get()
        if item is None:
            break
        idx, offset, audio = item
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5)) as c:
                r = (await c.post(URL + "/stt" + (f"?lang={m['lang']}" if m["lang"] else ""), content=audio)).json()
            for s in r.get("segments", []):
                if s["text"]:
                    m["lines"].append({"t": round(offset + s["start"], 1), "text": s["text"]})
            m["language"] = r.get("language") or m["language"]
        except Exception as e:
            m["errors"] += 1
            m["lines"].append({"t": offset, "text": f"[piece {idx} could not be transcribed: {type(e).__name__}]"})
        m["done_pieces"] += 1
    m["worker_done"].set()


class StartIn(BaseModel):
    lang: str = ""            # "" = detect


@router.post("/api/live/start")
async def live_start(b: StartIn):
    await _ensure_stt()
    mid = uuid.uuid4().hex[:12]
    meetings[mid] = {"id": mid, "started": time.time(), "lang": b.lang, "language": "", "lines": [], "pieces": 0,
                     "done_pieces": 0, "errors": 0, "status": "live", "queue": asyncio.Queue(),
                     "worker_done": asyncio.Event(), "result": None}
    asyncio.create_task(_worker(mid))
    return {"id": mid}


@router.post("/api/live/{mid}/chunk")
async def live_chunk(mid: str, file: UploadFile = File(...), idx: int = Form(0), offset: float = Form(0.0)):
    m = meetings.get(mid)
    if not m or m["status"] != "live":
        raise HTTPException(404, "no live meeting")
    m["pieces"] += 1
    await m["queue"].put((idx, offset, await file.read()))
    return {"queued": m["pieces"] - m["done_pieces"]}


@router.get("/api/live/{mid}")
async def live_get(mid: str, after: int = 0):
    m = meetings.get(mid)
    if not m:
        raise HTTPException(404)
    return {"id": mid, "status": m["status"], "language": m["language"], "lines": m["lines"][after:], "total": len(m["lines"]),
            "behind": m["pieces"] - m["done_pieces"], "elapsed": round(time.time() - m["started"]), "result": m["result"]}


class AskIn(BaseModel):
    question: str


@router.post("/api/live/{mid}/ask")
async def live_ask(mid: str, b: AskIn):
    m = meetings.get(mid)
    if not m:
        raise HTTPException(404)
    from . import research
    tx = "\n".join(f"[{int(l['t']) // 60}:{int(l['t']) % 60:02d}] {l['text']}" for l in m["lines"])[-40000:]
    if not tx:
        return {"answer": "Nothing has been transcribed yet - wait a few seconds."}
    ans = await research._llm([
        {"role": "system", "content": "You help the user during a meeting that is still going on. Answer from the transcript "
                                      "only, briefly, in the language of the question; quote times like [12:30] when useful."},
        {"role": "user", "content": f"Live transcript so far:\n{tx}\n\nQuestion: {b.question}"}], 600)
    return {"answer": ans}


class StopIn(BaseModel):
    add_tasks: bool = True


@router.post("/api/live/{mid}/stop")
async def live_stop(mid: str, b: StopIn):
    m = meetings.get(mid)
    if not m:
        raise HTTPException(404)
    if m["status"] == "live":
        m["status"] = "finishing"
        await m["queue"].put(None)
        asyncio.create_task(_finish(mid, b.add_tasks))
    return {"status": m["status"]}


async def _finish(mid: str, add_tasks: bool):
    m = meetings[mid]
    try:
        await m["worker_done"].wait()
        text = "\n".join(l["text"] for l in m["lines"] if not l["text"].startswith("[piece"))
        if not text.strip():
            raise RuntimeError("no speech was recognized")
        from . import notes
        segs = [{"start": l["t"], "text": l["text"]} for l in m["lines"]]
        m["result"] = await notes.finalize(text, segs, m["language"], time.time() - m["started"], add_tasks, "Meeting")
        m["status"] = "done"
    except Exception as e:
        m["status"] = "error"
        m["result"] = {"error": f"{type(e).__name__}: {e}"}
