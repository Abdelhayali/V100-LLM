"""Document OCR with baidu/Unlimited-OCR as a sub-model (the ocr_document tool).

The OCR model (~7 GB, Transformers) runs in its own Python environment in <app>/ocr, one process per request
(ocr/ocr_worker.py), so nothing stays in memory afterwards. Modes, chosen in the apps per chat:
  gpu - the V100 is shared: unload the chat model, read on the GPU (fast), load the chat model again
  cpu - read on the CPU (slower) while the chat model stays loaded on the GPU
  off - no OCR tool
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import db, models_ctl, tools
from .config import DATA_DIR, SERVER_DIR, config

MODES = ("off", "gpu", "cpu")
_lock = asyncio.Lock()   # one OCR at a time (GPU or ~14 GB of RAM each)


def ocr_dir() -> Path:
    return Path(config.data.get("ocr_dir") or (SERVER_DIR.parent / "ocr"))


def ready() -> tuple[bool, str]:
    d = ocr_dir()
    py = d / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        return False, f"the OCR environment is not installed ({py} missing; run ocr/setup-ocr.bat)"
    if not (d / "model" / "model.safetensors").exists():
        return False, f"the Unlimited-OCR model is not downloaded ({d / 'model'}; run ocr/setup-ocr.bat)"
    return True, ""


def schema() -> dict:
    return tools._fn(
        "ocr_document",
        "Read a scanned PDF, a photo of a page, a screenshot or any image with text using a dedicated OCR model "
        "(Unlimited-OCR). Returns the text as markdown, with tables, formulas and the reading order kept, in any "
        "language (English, Arabic, ...). Use it when read_file gives no text (scanned PDF), for documents in images, "
        "or when you need the exact text of an image. It takes a while (tens of seconds to minutes per page), so "
        "read only the pages you need.",
        {"path": {"type": "string", "description": "The image or PDF file (attachments show their saved path)"},
         "pages": {"type": "string", "description": "PDF pages, e.g. '1-3,7' (default: all, at most 20)"}},
        ["path"])


def _attachment(p: str) -> Path | None:
    """A file the user attached in the chat (kept in the bridge's uploads folder, outside the allowed folders):
    by its saved path, or by its file name (newest upload of that name)."""
    up = (DATA_DIR / "uploads").resolve()
    if not p:
        return None
    try:
        q = Path(p).resolve()
        if q.is_file() and q.is_relative_to(up):
            return q
    except OSError:
        pass
    name = Path(p).name
    hits = sorted((x for x in up.glob("*_" + name) if x.is_file()), key=lambda x: x.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


async def _wait_vram_free(limit_mb: int = 2500, timeout: float = 60):
    t = time.time()
    while time.time() - t < timeout:
        try:
            s = await models_ctl._get("/api/status", timeout=5)
            if (s.get("gpu") or {}).get("used", 0) < limit_mb:
                return
        except Exception:
            return
        await asyncio.sleep(1)


async def _wait_model_ready(timeout: float = 600):
    t = time.time()
    while time.time() - t < timeout:
        try:
            s = await models_ctl._get("/api/status", timeout=5)
            if s.get("health") == "ready":
                return True
            if s.get("exit") is not None:
                return False
        except Exception:
            pass
        await asyncio.sleep(2)
    return False


LIMIT_S = {"cuda": 600, "cpu": 2400}
_current = {"pid": None}                 # the running worker, killed when the user stops the reply   # per file; a stuck OCR is stopped so the chat model always comes back


def _kill_tree(pid: int):
    """The venv's python.exe starts the real interpreter as a child: kill both, or the child keeps the GPU."""
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _worker(device: str, path: Path, pages: str) -> dict:
    d = ocr_dir()
    out = Path(tempfile.mkdtemp(prefix="ocr_")) / "result.json"
    cmd = [str(d / ".venv" / "Scripts" / "python.exe"), str(d / "ocr_worker.py"), "--device", device,
           "--input", str(path), "--out", str(out)]
    if pages:
        cmd += ["--pages", pages]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    p = subprocess.Popen(cmd, cwd=str(d), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _current["pid"] = p.pid
    try:
        _, err = p.communicate(timeout=LIMIT_S[device])
    except subprocess.TimeoutExpired:
        _kill_tree(p.pid)
        p.communicate()
        return {"ok": False, "error": f"stopped after {LIMIT_S[device] // 60} minutes (the page is too large or "
                                      "the OCR model got stuck); try the other OCR mode or a smaller image"}
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    return {"ok": False, "error": f"the OCR process exited with code {p.returncode}: "
                                  f"{err.decode('utf-8', 'replace')[-1500:]}"}


async def _worker_with_progress(device: str, path: Path, pages: str, emit, stopped=lambda: False) -> dict:
    """Run the worker; every 30 s tell the chat it is still working (else a long page looks like a hang), and kill it
    as soon as the user stops the reply."""
    task = asyncio.ensure_future(asyncio.to_thread(_worker, device, path, pages))
    t0 = last = time.time()
    while True:
        try:
            return await asyncio.wait_for(asyncio.shield(task), 2)
        except asyncio.TimeoutError:
            if stopped():
                if _current["pid"]:
                    await asyncio.to_thread(_kill_tree, _current["pid"])
                await task
                return {"ok": False, "error": "stopped by the user"}
            if time.time() - last >= 30:
                last = time.time()
                emit(f"OCR still reading… {int(last - t0)} s")
        except asyncio.CancelledError:      # reply stopped from the phone: stop the OCR process too
            if _current["pid"]:
                await asyncio.to_thread(_kill_tree, _current["pid"])
            raise


async def run(mode: str, args: dict, emit) -> str:
    """The ocr_document tool. emit(text) shows progress notes in the chat."""
    if mode not in ("gpu", "cpu"):
        return "OCR is switched off in the app (settings: OCR sub-model)."
    path = _attachment(args.get("path", ""))
    if path is None:
        try:
            path = tools.resolve_path(args.get("path", ""))
        except Exception as e:
            return f"Error: {e}"
    if not path.is_file():
        return f"Error: not a file: {path}"
    return (await run_files(mode, [path], emit, str(args.get("pages") or "").strip()))[0]


async def run_files(mode: str, paths: list[Path], emit, pages: str = "", stopped=lambda: False) -> list[str]:
    """OCR several files with one GPU swap (unload the chat model once, read all files, load it again)."""
    ok, why = ready()
    if not ok:
        return ["OCR is not available: " + why] * len(paths)
    out = []
    async with _lock:
        reload = None
        if mode == "gpu":
            try:
                s = await models_ctl._get("/api/status", timeout=8)
            except Exception:
                s = {}
            if s.get("model") and s.get("health") in ("ready", "loading", "starting"):
                reload = (s["model"], s.get("preset") or "")
                emit("OCR on the GPU: unloading the chat model for a moment…")
                await models_ctl._post("/api/stop", {})
            await _wait_vram_free()
        else:
            emit("OCR on the CPU (the chat model stays loaded)…")
        try:
            await _read_all(mode, paths, pages, emit, out, stopped)
        finally:
            if reload:   # also when the reply was stopped: the chat model must come back
                await asyncio.shield(_reload(reload, emit))
    return out


async def _reload(reload, emit):
    emit("Loading the chat model again…")
    try:
        await models_ctl.load(models_ctl.LoadIn(id=reload[0], preset=reload[1]))
        if not await _wait_model_ready():
            emit("The chat model did not come back; load it again from the Models screen.")
    except Exception as e:
        emit(f"Could not reload the chat model ({e}); load it again from the Models screen.")


async def _read_all(mode, paths, pages, emit, out, stopped):
        for path in paths:
            if stopped():
                out.append("OCR failed: stopped by the user")
                continue
            emit(f"Reading {path.name.split('_', 1)[-1]} with OCR…")
            t0 = time.time()
            try:
                res = await _worker_with_progress("cuda" if mode == "gpu" else "cpu", path, pages, emit, stopped)
            except Exception as e:
                res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            if not res.get("ok"):
                out.append("OCR failed: " + (res.get("error") or "unknown error"))
                emit(out[-1][:300])
                continue
            n = len(res.get("pages") or [])
            note = (f"[OCR of {path.name.split('_', 1)[-1]}: {n} page(s), {res.get('seconds', round(time.time() - t0))} s on "
                    f"{'GPU' if mode == 'gpu' else 'CPU'}" + (f"; {res['error']}" if res.get("error") else "") + "]\n\n")
            out.append(tools.truncate(note + (res.get("text") or "(no text found)"), 60_000))
            emit(f"OCR done: {n} page(s) in {res.get('seconds')} s")


# ---- automatic OCR of attachments (OCR set to A or B: every attached image / PDF is read, whatever the model does)
db._conn.execute("CREATE TABLE IF NOT EXISTS attachment_ocr(attachment_id TEXT PRIMARY KEY, text TEXT, created REAL)")
db._conn.commit()


def ocr_text(aid) -> str:
    r = db._q("SELECT text FROM attachment_ocr WHERE attachment_id=?", (str(aid),), one=True)
    return r["text"] if r else ""


async def auto_ocr(mode: str, attachment_ids: list, emit, stopped=lambda: False) -> int:
    """Read the message's images and PDFs with OCR once (cached per attachment). Returns how many were read."""
    if mode not in ("gpu", "cpu"):
        return 0
    todo = []
    for aid in attachment_ids:
        a = db.get_attachment(aid)
        if a and a["kind"] in ("image", "pdf") and not ocr_text(aid) and Path(a["path"]).is_file():
            todo.append(a)
    if not todo:
        return 0
    results = await run_files(mode, [Path(a["path"]) for a in todo], emit, stopped=stopped)
    n = 0
    for a, text in zip(todo, results):
        if text.startswith("[OCR of"):
            db._q("INSERT OR REPLACE INTO attachment_ocr VALUES(?,?,?)", (str(a["id"]), text, time.time()))
            n += 1
    return n
