"""Meeting / voice notes: the phone records, the PC transcribes (faster-whisper large-v3-turbo, Arabic + English) and the
chat model writes a title, summary, key points, decisions and action items. Action items can go to the task list.

Each note becomes a chat ("🎙 title") with the summary and the full transcript (also a .md file in workspace/notes),
and the phone gets a notification. Transcription runs on the CPU by default, so the chat model stays loaded.
"""
import asyncio
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from . import db, schedules, tools
from .config import DATA_DIR, config

router = APIRouter()
jobs: dict[str, dict] = {}
_lock = asyncio.Lock()


def _ocr_dir() -> Path:
    from . import ocr
    return ocr.ocr_dir()


def _transcribe(audio: Path, device: str) -> dict:
    d = _ocr_dir()
    out = Path(tempfile.mkdtemp(prefix="stt_")) / "result.json"
    cmd = [str(d / ".venv" / "Scripts" / "python.exe"), str(d / "transcribe_worker.py"), "--audio", str(audio),
           "--out", str(out), "--device", device]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", HF_HUB_OFFLINE="1")
    p = subprocess.run(cmd, cwd=str(d), env=env, capture_output=True, timeout=4 * 3600,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    return {"ok": False, "error": f"transcriber exited with code {p.returncode}: " + p.stderr.decode("utf-8", "replace")[-800:]}


def _clock(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


async def _summarize(text: str, lang: str) -> dict:
    from . import research
    raw = await research._llm([
        {"role": "system", "content": "You turn meeting and voice-note transcripts into clear notes. Reply with JSON only."},
        {"role": "user", "content": "Transcript" + (f" (language: {lang})" if lang else "") + ":\n\n" + text[:60000] +
         "\n\nReply with a JSON object: {\"title\": short title, \"summary\": 3-6 sentences, \"key_points\": [..], "
         "\"decisions\": [..], \"action_items\": [{\"task\": .., \"owner\": .. or \"\", \"due\": YYYY-MM-DD or \"\"}]}. "
         "Write everything in the transcript's language. Leave lists empty if there is nothing."}], 2500, think=True)
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {"title": "", "summary": raw[:2000]}


async def _process(jid: str, audio: Path, device: str, add_tasks: bool):
    j = jobs[jid]
    try:
        async with _lock:
            j["progress"] = "transcribing" + (" on the GPU" if device == "cuda" else " on the CPU (chat model stays loaded)")
            reload = None
            if device == "cuda":     # same swap as OCR: free the GPU, transcribe, load the chat model again
                from . import models_ctl
                s = await models_ctl._get("/api/status", timeout=8)
                if s.get("model") and s.get("health") == "ready":
                    reload = (s["model"], s.get("preset") or "")
                    await models_ctl._post("/api/stop", {})
                    await asyncio.sleep(4)
            try:
                res = await asyncio.to_thread(_transcribe, audio, device)
            finally:
                if reload:
                    from . import models_ctl, ocr
                    await models_ctl.load(models_ctl.LoadIn(id=reload[0], preset=reload[1]))
                    await ocr._wait_model_ready()
        if not res.get("ok"):
            raise RuntimeError(res.get("error") or "transcription failed")
        text, lang = res.get("text", ""), res.get("language", "")
        if not text.strip():
            raise RuntimeError("no speech was found in the recording")
        j["progress"] = "writing the summary"
        notes = await _summarize(text, lang)
        title = (notes.get("title") or "Voice note").strip()[:70]
        md = [f"# {title}", f"*{time.strftime('%Y-%m-%d %H:%M')} · {_clock(res.get('duration', 0))} · {lang}*", "",
              "## Summary", str(notes.get("summary", "")).strip(), ""]
        for key, head in (("key_points", "Key points"), ("decisions", "Decisions")):
            if notes.get(key):
                md += [f"## {head}"] + [f"- {x}" for x in notes[key]] + [""]
        items = [x for x in notes.get("action_items") or [] if isinstance(x, dict) and x.get("task")]
        if items:
            md += ["## Action items"] + [f"- [ ] {x['task']}" + (f" — {x['owner']}" if x.get("owner") else "") +
                                         (f" (due {x['due']})" if x.get("due") else "") for x in items] + [""]
        md += ["## Transcript"] + [f"`{_clock(s['start'])}` {s['text']}" for s in res.get("segments", [])]
        body = "\n".join(md)
        out_dir = Path(config["workspace"]) / "notes"
        out_dir.mkdir(parents=True, exist_ok=True)
        f = out_dir / f"{time.strftime('%Y-%m-%d-%H%M')}-{re.sub(r'[^\w]+', '-', title.lower())[:40].strip('-') or 'note'}.md"
        f.write_text(body, encoding="utf-8")
        sess = db.create_session("🎙 " + title, "")
        db.add_message(sess["id"], "user", f"Voice note ({_clock(res.get('duration', 0))}) - please keep these notes.")
        db.add_message(sess["id"], "assistant", body, attachments=[tools.share_file(f)])
        added = 0
        if add_tasks and items:
            from . import organizer
            for x in items:
                try:
                    organizer.task_save(title=x["task"] + (f" ({x['owner']})" if x.get("owner") else ""), due=x.get("due") or None, notes="from a voice note")
                    added += 1
                except Exception:
                    pass
        j.update(status="done", progress="done", session_id=sess["id"], title=title, tasks_added=added,
                 duration=res.get("duration", 0), stt_seconds=res.get("seconds", 0))
        schedules.notify("note", "🎙 " + title, f"Summary ready · {len(items)} action items" +
                         (f", {added} added to tasks" if added else ""), sess["id"])
    except Exception as e:
        j.update(status="error", progress="failed", error=f"{type(e).__name__}: {e}")
        schedules.notify("note", "🎙 Voice note failed", j["error"][:200])


@router.post("/api/notes/voice")
async def voice_note(file: UploadFile = File(...), device: str = Form("cpu"), add_tasks: bool = Form(True)):
    if not (_ocr_dir() / "transcribe_worker.py").exists():
        raise HTTPException(503, "speech-to-text is not installed (ocr/setup-ocr.bat)")
    d = DATA_DIR / "uploads" / "voice"
    d.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "note.m4a").suffix or ".m4a"
    audio = d / f"{uuid.uuid4().hex[:10]}{ext}"
    with open(audio, "wb") as fh:
        while chunk := await file.read(1 << 20):
            fh.write(chunk)
    jid = audio.stem
    jobs[jid] = {"id": jid, "status": "running", "progress": "queued", "started": time.time(), "size": audio.stat().st_size,
                 "session_id": "", "title": "", "error": ""}
    asyncio.create_task(_process(jid, audio, "cuda" if device == "gpu" else "cpu", add_tasks))
    return jobs[jid]


@router.get("/api/notes/voice")
async def voice_jobs():
    return sorted(jobs.values(), key=lambda j: -j["started"])
