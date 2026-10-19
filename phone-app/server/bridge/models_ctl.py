"""Model control through the V100-LLM launcher (D:\\V100-LLM, START-GUI.bat): list models, load, unload, live status.

The launcher runs on the PC at launcher_url (default http://127.0.0.1:7860) and serves the loaded model's
OpenAI-compatible API on its own port (8899), which is what llm_base_url points at. Everything here only proxies the
launcher's own API, so the phone does exactly what the launcher GUI does.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .config import config

router = APIRouter(prefix="/api/v100")


def _base() -> str:
    return (config.data.get("launcher_url") or "http://127.0.0.1:7860").rstrip("/")


async def _get(path: str, timeout: float = 10):
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.get(_base() + path)
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict, timeout: float = 30):
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(_base() + path, json=body)
        r.raise_for_status()
        return r.json()


async def _reachable() -> bool:
    try:
        await _get("/api/status", timeout=3)
        return True
    except Exception:
        return False


async def _ensure_launcher() -> None:
    """Start the launcher (hidden, no browser) if it is not running, using its own portable Python."""
    if await _reachable():
        return
    d = Path(config.data.get("launcher_dir") or r"D:\V100-LLM")
    py, script = d / "runtime" / "python" / "python.exe", d / "gui" / "launcher.py"
    if not script.exists():
        raise HTTPException(503, f"V100-LLM launcher not found in {d} (set launcher_dir in server/config.json)")
    exe = str(py) if py.exists() else sys.executable
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([exe, str(script), "--no-browser"], cwd=str(d), creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    for _ in range(30):
        await asyncio.sleep(1)
        if await _reachable():
            return
    raise HTTPException(503, "The V100-LLM launcher did not start")


@router.get("/status")
async def status():
    """What is loaded, plus GPU / CPU / RAM, refreshed by the phone every few seconds."""
    try:
        s = await _get("/api/status", timeout=8)
    except Exception:
        return {"launcher": False, "health": "offline"}
    name = preset_name = ""
    if s.get("model"):
        try:
            cat = (await _get("/api/catalog"))["catalog"]
            m = next((x for x in cat["models"] if x["id"] == s["model"]), None)
            if m:
                name = m["name"]
                preset_name = next((p["name"] for p in m["presets"] if p["id"] == s.get("preset")), s.get("preset") or "")
        except Exception:
            pass
    sysi, gpu = s.get("sys") or {}, s.get("gpu") or {}
    return {
        "launcher": True, "health": s.get("health", "stopped"), "model": s.get("model") or "", "model_name": name,
        "preset": s.get("preset") or "", "preset_name": preset_name, "kernel": s.get("kernel") or "",
        "port": s.get("port") or 0, "uptime": s.get("uptime") or 0,
        "gpu_name": gpu.get("name", ""), "vram_used_mb": gpu.get("used", 0), "vram_total_mb": gpu.get("total", 0),
        "gpu_util": gpu.get("util", 0),
        "gpu_temp": gpu.get("temp"), "gpu_power": gpu.get("power"), "gpu_power_limit": gpu.get("power_limit"),
        "gpu_clock": gpu.get("clock"), "gpu_clock_max": gpu.get("clock_max"), "gpu_throttle": gpu.get("throttle") or [],
        "cpu_temp": sysi.get("cpu_temp"), "cpu_temp_source": sysi.get("cpu_temp_source") or "",
        "cpu": sysi.get("cpu") or 0.0, "cpu_threads": sysi.get("cpu_threads") or 0,
        "ram_used": sysi.get("ram_used") or 0, "ram_total": sysi.get("ram_total") or 0,
        "model_ram": sysi.get("model_ram") or 0,
        "log": [x for x in (s.get("log") or [])][-6:],
    }


@router.get("/models")
async def models():
    """Every model in the V100-LLM catalog with its presets and whether its files are on disk."""
    await _ensure_launcher()
    d = await _get("/api/catalog")
    cat, st = d["catalog"], d.get("status") or {}
    out = []
    for m in cat["models"]:
        files = (st.get(m["id"]) or {}).get("files") or []
        size = sum((f.get("size") or 0) for f in files if "mmproj" not in str(f.get("name", "")))
        out.append({
            "id": m["id"], "name": m["name"], "desc": m.get("desc", ""),
            "installed": bool(files) and all(f.get("have") for f in files),
            "size_gb": round(size / 1e9, 1) if size else 0.0,
            "vision": bool(m.get("mmproj")) or bool(m.get("strata")),
            "presets": [{"id": p["id"], "name": p["name"], "bench": p.get("bench", "")} for p in m.get("presets", [])],
        })
    return out


class LoadIn(BaseModel):
    id: str
    preset: str = ""


@router.post("/load")
async def load(body: LoadIn):
    """Load a model with one of its tuned presets (the launcher's recommended parameters)."""
    await _ensure_launcher()
    cat = (await _get("/api/catalog"))["catalog"]
    m = next((x for x in cat["models"] if x["id"] == body.id), None)
    if not m:
        raise HTTPException(404, f"unknown model {body.id}")
    p = next((x for x in m["presets"] if x["id"] == body.preset), None) or (m["presets"] or [None])[0]
    if not p:
        raise HTTPException(400, "this model has no preset")
    params = [{"flag": x[0], "value": x[1], "on": True} for x in p["params"]]
    r = await _post("/api/start", {"id": m["id"], "preset": p["id"], "kernel": p["kernel"], "params": params})
    if not r.get("ok", True):
        raise HTTPException(500, r.get("error") or "the launcher refused to start the model")
    return {"ok": True, "model": m["id"], "preset": p["id"]}


@router.post("/unload")
async def unload():
    """Stop the loaded model and free the GPU."""
    if not await _reachable():
        return {"ok": True}
    await _post("/api/stop", {})
    return {"ok": True}

@router.post("/free_gpu")
async def free_gpu():
    """The app's Free GPU button: unload the model, stop a running OCR (without loading the chat model again), and end
    any other V100-LLM / OCR process that still holds GPU memory. Other programs on the GPU are never touched."""
    from . import ocr
    before = _gpu_used()
    stopped_ocr = await asyncio.to_thread(ocr.free_gpu_now)
    if await _reachable():
        try:
            await _post("/api/stop", {})
        except Exception:
            pass
    roots = [str(Path(config.data.get("launcher_dir") or r"D:\V100-LLM")).lower(), str(ocr.ocr_dir()).lower()]
    killed = []
    for pid, name in _gpu_apps():
        cmd = _cmdline(pid).lower()
        if any(r in name.lower() or r in cmd for r in roots) or "ocr_worker.py" in cmd:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            killed.append(Path(name).name or str(pid))
    for _ in range(20):
        await asyncio.sleep(0.5)
        if _gpu_used() < 1000:
            break
    after = _gpu_used()
    return {"ok": True, "before_mb": before, "after_mb": after, "stopped_ocr": stopped_ocr, "killed": killed}


def _gpu_used() -> int:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return int(out.split()[0])
    except Exception:
        return -1


def _gpu_apps() -> list[tuple[int, str]]:
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return []
    apps = []
    for line in out.splitlines():
        pid, _, name = line.partition(",")
        if pid.strip().isdigit():
            apps.append((int(pid), name.strip()))
    return apps


def _cmdline(pid: int) -> str:
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command",
                               f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                              capture_output=True, text=True, timeout=15,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return ""
