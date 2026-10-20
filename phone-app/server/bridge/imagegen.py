"""Image generation with Qwen-Image-2512 on the shared V100 (stable-diffusion.cpp, GGUF).

The chat model gets a `generate_image` tool. When it is called, the chat model is unloaded (the V100 has room for one
of them), stable-diffusion.cpp makes the picture with the 8-step Lightning LoRA, the chat model is loaded again and
the reply continues with the image shown in the chat. Files: ocr/image (ocr/get-image-model.py downloads them).
"""
import asyncio
import random
import re
import subprocess
import time
from pathlib import Path

from . import models_ctl, ocr, tools
from .config import config

SIZES = {"square": (1024, 1024), "landscape": (1216, 832), "portrait": (832, 1216), "wide": (1344, 768)}
LIMIT_S = 900
_current = {"pid": None}


def idir() -> Path:
    return ocr.ocr_dir() / "image"


def _find() -> dict | None:
    d = idir()
    if not d.exists():
        return None
    exe = next(d.glob("sd/**/sd-cli.exe"), None) or next(d.glob("sd/**/sd.exe"), None)
    model = next(iter(sorted(d.glob("qwen-image-2512-*.gguf"))), None)
    te = next(d.glob("Qwen2.5-VL-7B-Instruct-*.gguf"), None)
    vae = d / "qwen_image_vae.safetensors"
    lora = next(d.glob("lora/*Lightning-8steps*.safetensors"), None)
    if not (exe and model and te and vae.exists()):
        return None
    return {"exe": exe, "model": model, "te": te, "vae": vae, "lora": lora}


def ready() -> bool:
    return _find() is not None


def schema() -> dict:
    return tools._fn(
        "generate_image",
        "Create a picture with the image generator on the user's PC (Qwen-Image; takes about a minute, the chat model is "
        "unloaded meanwhile). Write `prompt` in English as a detailed description: subject, setting, style, lighting, "
        "composition, colours, and any text that must appear in the image (in quotes; Qwen-Image renders English and "
        "Chinese text well). The picture is shown to the user automatically.",
        {"prompt": {"type": "string"},
         "size": {"type": "string", "enum": list(SIZES), "description": "default square"},
         "negative": {"type": "string", "description": "things to avoid (optional)"},
         "seed": {"type": "integer", "description": "repeat a picture with the same seed (optional)"}},
        ["prompt"])


def _kill():
    if _current["pid"]:
        ocr._kill_tree(_current["pid"])


def _run(f: dict, prompt: str, negative: str, w: int, h: int, seed: int, out: Path, emit) -> tuple[bool, str]:
    lora = f["lora"]
    steps, cfg = (8, 1.0) if lora else (40, 2.5)
    p = prompt + (f" <lora:{lora.stem}:1>" if lora else "")
    cmd = [str(f["exe"]), "--diffusion-model", str(f["model"]), "--vae", str(f["vae"]), "--llm", str(f["te"]),
           "-p", p, "--cfg-scale", str(cfg), "--sampling-method", "euler", "--steps", str(steps), "--flow-shift", "3",
           "-W", str(w), "-H", str(h), "--seed", str(seed), "--diffusion-fa", "--offload-to-cpu", "--vae-tiling",
           "-o", str(out)]
    if lora:
        cmd[1:1] = ["--lora-model-dir", str(lora.parent)]
    if negative:
        cmd += ["-n", negative]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(f["exe"].parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _current["pid"] = proc.pid
    tail, last = [], ""
    try:
        with out.with_suffix(".log").open("w", encoding="utf-8") as lf:
            for line in proc.stdout:
                lf.write(line)
                tail = (tail + [line.rstrip()])[-25:]
                m = re.search(r"\|\s*(\d+)/(\d+)\b", line)
                if m and int(m.group(2)) == steps and m.group(0) != last:   # only the sampling steps
                    last = m.group(0)
                    emit(f"Drawing the picture: step {m.group(1)}/{m.group(2)}")
                if time.time() - t0 > LIMIT_S:
                    _kill()
                    return False, "stopped: took longer than 15 minutes"
        proc.wait()
    finally:
        _current["pid"] = None
    if proc.returncode == 0 and out.exists():
        return True, f"{time.time() - t0:.0f} s"
    return False, "\n".join(tail[-8:]) or f"exit {proc.returncode}"


async def generate(args: dict, emit, stopped=lambda: False) -> tuple[str, list]:
    f = _find()
    if not f:
        return ("The image generator is not installed on the PC (run ocr\\get-image-model.py). Tell the user.", [])
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return ("Give a prompt describing the picture.", [])
    w, h = SIZES.get(str(args.get("size") or "square"), SIZES["square"])
    seed = int(args.get("seed") or random.randint(1, 2**31 - 1))
    out_dir = Path(config["workspace"]) / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower())[:40].strip("-") or "image"
    out = out_dir / f"{time.strftime('%Y-%m-%d-%H%M%S')}-{slug}.png"
    # sd-cli reads its arguments in the ANSI code page: draw to a plain-ASCII path, then move it to its real name
    tmp_dir = idir() / "_out"
    tmp_dir.mkdir(exist_ok=True)
    tmp = tmp_dir / f"img-{int(time.time() * 1000)}.png"
    async with ocr._lock:            # one GPU swap at a time (OCR, voice notes, images)
        ocr._freed["on"] = False
        reload = None
        try:
            s = await models_ctl._get("/api/status", timeout=8)
        except Exception:
            s = {}
        if s.get("model") and s.get("health") in ("ready", "loading", "starting"):
            reload = (s["model"], s.get("preset") or "")
            emit("Making the image: unloading the chat model for a moment…")
            await models_ctl._post("/api/stop", {})
        await ocr._wait_vram_free()
        try:
            if stopped():
                return ("Stopped by the user.", [])
            ok, info = await asyncio.to_thread(_run, f, prompt, str(args.get("negative") or ""), w, h, seed, tmp, emit)
            import shutil                               # shutil.move: _out is on the image drive, out maybe on another
            if ok:
                shutil.move(str(tmp), str(out))
            if tmp.with_suffix(".log").exists():      # the run's full log, next to the picture
                shutil.move(str(tmp.with_suffix(".log")), str(out.with_suffix(".log")))
        finally:
            if reload and not ocr._freed["on"]:
                await asyncio.shield(ocr._reload(reload, emit))
    if not ok:
        return (f"The image could not be made: {info}", [])
    att = tools.share_file(out)
    return (f"The image was made in {info} ({w}x{h}, seed {seed}) and is shown to the user; saved as {out}. "
            "Describe it in one or two sentences and offer a change if useful (same seed + changed prompt).", [att])
