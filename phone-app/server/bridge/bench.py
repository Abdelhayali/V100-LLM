"""Benchmark the loaded model from the phone: a quick speed test and any categories of the V100-LLM hard suite.

Runs eval/run_eval_hard.py of the launcher folder against the model that is already loaded (the model stays loaded) and
writes to eval/results_phone, so the published leaderboard (results_hard) is never changed from the phone.
"""
import asyncio
import json
import re
import subprocess
import threading
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import models_ctl
from .config import config, llm_api_base

router = APIRouter(prefix="/api/v100/bench")
CATS = ["coding", "reasoning", "ifeval", "search", "agent", "vision", "longctx"]
state: dict = {"running": False, "started": 0.0, "model": "", "preset": "", "log": [], "scores": {}, "speed": {},
               "done": 0.0, "error": "", "proc": None}
SPEED_PROMPTS = [("code", "Write a Python function that parses a CSV file and returns the average of a numeric column, "
                          "with error handling."),
                 ("chat", "Explain in a few paragraphs why the sky is blue and why sunsets are red.")]


def _launcher_dir() -> Path:
    return Path(config.data.get("launcher_dir") or r"D:\V100-LLM")


class BenchIn(BaseModel):
    categories: list[str] = []
    speed: bool = True


def _log(s: str):
    state["log"].append(s)
    state["log"] = state["log"][-200:]


async def _speed():
    tps = {}
    async with httpx.AsyncClient(timeout=600) as c:
        for name, prompt in SPEED_PROMPTS:
            r = await c.post(llm_api_base() + "/chat/completions", json={
                "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False, "reasoning_strength": "low"}})
            t = r.json().get("timings") or {}
            tps[name] = round(t.get("predicted_per_second") or 0, 1)
            _log(f"speed {name}: {tps[name]} tok/s")
    if tps:
        tps["mean"] = round(sum(tps.values()) / len(tps), 1)
        _log(f"speed mean: {tps['mean']} tok/s")
    state["speed"] = tps


def _suite(cats: list[str], label: str):
    d = _launcher_dir()
    py = d / "runtime" / "python" / "python.exe"
    skip = [c for c in CATS if c not in cats]
    cmd = [str(py), str(d / "eval" / "run_eval_hard.py"), "--label", label, "--out-dir", "results_phone"]
    if skip:
        cmd += ["--skip"] + skip
    p = subprocess.Popen(cmd, cwd=str(d / "eval"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    state["proc"] = p
    for line in p.stdout:
        line = line.rstrip()
        m = re.match(r"\s*(\w+)\s+([\d.]+)\s+\((\d+)s\)", line)
        if m and m.group(1) in cats:
            state["scores"][m.group(1)] = float(m.group(2))
            _log(f"{m.group(1)}: {m.group(2)}  ({m.group(3)} s)")
        elif line.strip() and not line.strip().startswith("overall"):
            _log(line.strip()[:200])
    p.wait()
    state["proc"] = None
    if p.returncode not in (0, None) and not state["error"]:
        state["error"] = f"the test suite exited with code {p.returncode}"


async def _run(cats: list[str], speed: bool):
    try:
        if speed:
            _log("speed test (code + chat, 300 tokens each)…")
            await _speed()
        if cats:
            label = re.sub(r"[^\w.-]", "_", f"{state['model']}@{state['preset']}-{time.strftime('%Y%m%d-%H%M%S')}")
            _log("hard suite: " + ", ".join(cats) + " (coding ~2 min, reasoning ~2 min, the rest under a minute each)")
            await asyncio.to_thread(_suite, cats, label)
        if state["scores"]:
            state["scores"]["mean"] = round(sum(state["scores"].values()) / len(state["scores"]), 1)
            _log(f"mean of the chosen categories: {state['scores']['mean']}")
    except Exception as e:
        state["error"] = f"{type(e).__name__}: {e}"
        _log("error: " + state["error"])
    finally:
        state["running"] = False
        state["done"] = time.time()


@router.post("")
async def start(body: BenchIn):
    if state["running"]:
        raise HTTPException(409, "a benchmark is already running")
    cats = [c for c in body.categories if c in CATS]
    if not cats and not body.speed:
        raise HTTPException(400, "choose the speed test or at least one category")
    s = await models_ctl.status()
    if s.get("health") != "ready":
        raise HTTPException(409, "load a model first (Models tab)")
    state.update(running=True, started=time.time(), done=0.0, model=s.get("model", ""), preset=s.get("preset", ""),
                 model_name=s.get("model_name", ""), preset_name=s.get("preset_name", ""), log=[], scores={}, speed={},
                 error="", categories=cats)
    asyncio.create_task(_run(cats, body.speed))
    return {"ok": True}


@router.get("")
async def get():
    return {k: v for k, v in state.items() if k != "proc"} | {"elapsed": round(time.time() - state["started"]) if state["started"] else 0}


@router.post("/stop")
async def stop():
    p = state.get("proc")
    if p and p.poll() is None:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    state["error"] = state["error"] or "stopped"
    return {"ok": True}
