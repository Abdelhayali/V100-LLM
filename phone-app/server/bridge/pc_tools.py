"""PC actions: a few specific, approved things the AI may do on the PC when the user switches on "PC actions" for a chat.

There is no free mouse / keyboard control. Each action is a narrow tool, logged in the audit log:
  look_at_screen     screenshot + the vision model answers a question about it (the screenshot is shown to the user)
  open_on_pc         open a file / folder in the allowed folders, a web link, or one app from a short list
  move_file          move or rename inside the allowed folders (never overwrites)
  list_saved_scripts / run_saved_script   run one of the user's own scripts from workspace/scripts
open / move / run always ask the user, even with auto-approve on.
"""
import json
import os
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

from . import db, tools
from .config import config

TOOL_NAMES = {"look_at_screen", "open_on_pc", "move_file", "list_saved_scripts", "run_saved_script"}
ALWAYS_ASK = {"open_on_pc", "move_file", "run_saved_script"}
NEEDS_APPROVAL = {"look_at_screen"}
APPS = {"notepad": ["notepad.exe"], "calculator": ["calc.exe"], "calc": ["calc.exe"], "explorer": ["explorer.exe"],
        "file explorer": ["explorer.exe"], "paint": ["mspaint.exe"], "task manager": ["taskmgr.exe"],
        "settings": ["cmd", "/c", "start", "", "ms-settings:"], "snipping tool": ["cmd", "/c", "start", "", "ms-screenclip:"]}
SCRIPT_EXT = {".py", ".ps1", ".bat", ".cmd"}


def scripts_dir() -> Path:
    d = Path(config["workspace"]) / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def schemas() -> list[dict]:
    f = tools._fn
    return [
        f("look_at_screen", "Take a screenshot of the PC screen and look at it to answer a question (what is open, read an "
          "error message, describe a window). The screenshot is also shown to the user.",
          {"question": {"type": "string", "description": "What to find out from the screen"}}, ["question"]),
        f("open_on_pc", "Open something on the PC for the user: a file or folder inside the allowed folders, an http(s) "
          "link in the browser, or an app: " + ", ".join(sorted(APPS)) + ". The user approves every time.",
          {"target": {"type": "string", "description": "Path, URL or app name"}}, ["target"]),
        f("move_file", "Move or rename a file or folder inside the allowed folders (fails if the destination exists). "
          "The user approves every time.",
          {"source": {"type": "string"}, "destination": {"type": "string"}}, ["source", "destination"]),
        f("list_saved_scripts", "List the user's own saved scripts (workspace/scripts) that run_saved_script can run.", {}, []),
        f("run_saved_script", "Run one of the user's saved scripts by file name, with optional arguments. The user approves "
          "every time.", {"name": {"type": "string"}, "args": {"type": "string", "description": "Optional arguments"}}, ["name"]),
    ]


def _look(question: str) -> tuple[str, list[dict]]:
    import asyncio
    import httpx
    from . import app as A
    att = tools.take_screenshot()
    full = db.get_attachment(att["id"])
    uri = A.image_data_uri(full)

    async def ask():
        model = await A.pick_model(None)
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as c:
            r = await c.post(A.llm_api_base() + "/chat/completions", headers=A.llm_headers(), json={
                "model": model, "stream": False, "max_tokens": 900, "temperature": 0.2,
                "chat_template_kwargs": {"enable_thinking": False, "reasoning_strength": "low"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": f"This is a screenshot of the user's PC screen. {question}\nAnswer factually; "
                                             "quote any text you need exactly."},
                    {"type": "image_url", "image_url": {"url": uri}}]}]})
            r.raise_for_status()
            return A._strip_think(r.json()["choices"][0]["message"].get("content") or "")
    try:
        answer = asyncio.run(ask())
    except Exception as e:
        answer = f"(the model could not look at the image: {type(e).__name__}: {e}; the loaded model may have no vision)"
    return f"Screenshot taken and shown to the user. What it shows:\n{answer}", [att]


def _open(target: str) -> str:
    t = target.strip()
    if t.lower().startswith(("http://", "https://")):
        webbrowser.open(t)
        return f"Opened {t} in the browser."
    app = APPS.get(t.lower().removesuffix(".exe"))
    if app:
        subprocess.Popen(app, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if app[0] == "cmd" else 0)
        return f"Started {t}."
    p = tools.resolve_path(t)                 # only inside the allowed folders
    if not p.exists():
        return f"Error: not found: {p}"
    os.startfile(str(p))
    return f"Opened {p}."


def _move(src: str, dst: str) -> str:
    s, d = tools.resolve_path(src), tools.resolve_path(dst)
    if not s.exists():
        return f"Error: not found: {s}"
    if d.is_dir():
        d = d / s.name
    if d.exists():
        return f"Error: {d} already exists (nothing was overwritten)"
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(s), str(d))
    return f"Moved {s} -> {d}"


def _scripts() -> str:
    files = [f for f in sorted(scripts_dir().iterdir()) if f.suffix.lower() in SCRIPT_EXT]
    if not files:
        return f"No saved scripts yet. The user can put .py / .ps1 / .bat files in {scripts_dir()}."
    return "\n".join(f"{f.name}  ({f.stat().st_size} bytes, changed {time.strftime('%Y-%m-%d', time.localtime(f.stat().st_mtime))})"
                     for f in files)


def _run_script(name: str, args: str) -> str:
    f = (scripts_dir() / Path(name).name)       # file name only: no paths outside the scripts folder
    if not f.exists() or f.suffix.lower() not in SCRIPT_EXT:
        return f"Error: no saved script {name!r}. Use list_saved_scripts."
    import shlex
    a = shlex.split(args or "", posix=False)
    import sys
    cmd = {".py": [sys.executable, str(f)], ".ps1": ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(f)],
           ".bat": ["cmd", "/c", str(f)], ".cmd": ["cmd", "/c", str(f)]}[f.suffix.lower()] + a
    try:
        p = subprocess.run(cmd, cwd=str(scripts_dir()), capture_output=True, timeout=int(config["exec_timeout_sec"]) * 5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return "Error: the script took too long and was stopped."
    dec = lambda b: b.decode("utf-8", "replace") if b else ""
    return json.dumps({"exit_code": p.returncode, "stdout": tools.truncate(dec(p.stdout)), "stderr": tools.truncate(dec(p.stderr), 6000)},
                      ensure_ascii=False)


def execute(name: str, a: dict) -> tuple[str, list[dict]]:
    if name == "look_at_screen":
        return _look(str(a.get("question") or "What is on the screen?"))
    if name == "open_on_pc":
        return _open(str(a.get("target", ""))), []
    if name == "move_file":
        return _move(str(a.get("source", "")), str(a.get("destination", ""))), []
    if name == "list_saved_scripts":
        return _scripts(), []
    if name == "run_saved_script":
        return _run_script(str(a.get("name", "")), str(a.get("args", ""))), []
    return f"Unknown PC action {name}", []
