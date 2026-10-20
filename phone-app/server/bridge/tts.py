"""PC voices for read-aloud: proxies to ocr/tts_server.py (Piper, offline neural voices on the CPU), which the bridge
starts on first use and keeps running so the voices stay loaded."""
import asyncio
import os
import subprocess
import time

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()
PORT = 8781
URL = f"http://127.0.0.1:{PORT}"
_proc: subprocess.Popen | None = None
_lock = asyncio.Lock()


class TtsIn(BaseModel):
    text: str
    voice: str


async def _ensure():
    global _proc
    async with _lock:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                if (await c.get(URL + "/health")).status_code == 200:
                    return
        except Exception:
            pass
        from . import ocr
        d = ocr.ocr_dir()
        py, script = d / ".venv" / "Scripts" / "python.exe", d / "tts_server.py"
        if not script.exists() or not py.exists() or not (d / "piper").exists():
            raise HTTPException(503, "PC voices are not installed (ocr/setup-ocr.bat)")
        _proc = subprocess.Popen([str(py), str(script), "--port", str(PORT)], cwd=str(d),
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        t0 = time.time()
        while time.time() - t0 < 120:          # first start loads and warms up every voice
            await asyncio.sleep(1)
            try:
                async with httpx.AsyncClient(timeout=2) as c:
                    if (await c.get(URL + "/health")).status_code == 200:
                        return
            except Exception:
                pass
        raise HTTPException(503, "the PC voice server did not start")


@router.get("/api/tts/voices")
async def tts_voices():
    await _ensure()
    async with httpx.AsyncClient(timeout=10) as c:
        return (await c.get(URL + "/voices")).json()


@router.post("/api/tts")
async def tts(b: TtsIn):
    await _ensure()
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=5)) as c:
        r = await c.post(URL + "/tts", json={"text": b.text, "voice": b.voice})
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text[:300])
    return Response(r.content, media_type="audio/wav")
