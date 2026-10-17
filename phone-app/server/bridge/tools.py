"""Tools the LLM (and the phone app directly) can use: code execution, filesystem, memory."""
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from pathlib import Path

from . import db
from .config import config

MAX_OUT = 20_000

# Which chat session the current tool call belongs to (asyncio.to_thread copies context variables)
current_session: ContextVar[str | None] = ContextVar("current_session", default=None)
# Running code processes: pid -> info (shown in the app's "Running tasks" screen)
PROCS: dict[int, dict] = {}
_procs_lock = threading.Lock()


def list_procs() -> list[dict]:
    now = time.time()
    with _procs_lock:
        return [{**p, "elapsed": round(now - p["started"])} for p in PROCS.values()]


def kill_procs(session: str | None = None, pid: int | None = None) -> int:
    """Kill running code processes (and their children). session=None and pid=None kills all."""
    with _procs_lock:
        targets = [p for p in PROCS.values()
                   if (pid is None or p["pid"] == pid) and (session is None or p["session"] == session)]
    for p in targets:
        p["killed"] = True
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p["pid"])], capture_output=True)
    return len(targets)
TEXT_EXT = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".log", ".xml", ".html", ".css",
            ".yaml", ".yml", ".ini", ".cfg", ".toml", ".bat", ".ps1", ".c", ".h", ".cpp", ".java",
            ".kt", ".v", ".sv", ".vhd", ".tcl", ".sp", ".tex", ".sh", ".sql", ".rs", ".go"}


class ToolError(Exception):
    pass


# ---------------- path safety ----------------
def allowed_roots() -> list[str]:
    """Configured allowed folders; "*" means every drive of this PC (C:, D:, ...)."""
    roots = []
    for r in config["allowed_roots"]:
        if r == "*":
            roots += [d for d in os.listdrives() if Path(d).exists()]
        else:
            roots.append(r)
    return list(dict.fromkeys(roots))


def safe_name(name: str) -> str:
    """A single folder/file name (no path separators or Windows-reserved characters)."""
    name = (name or "").strip().rstrip(". ")
    if not name or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name in (".", ".."):
        raise ToolError('Invalid name (avoid \\ / : * ? " < > |)')
    return name[:200]


def resolve_path(p: str) -> Path:
    """Resolve p (absolute, or relative to the workspace) and ensure it is inside an allowed root."""
    if not p:
        raise ToolError("path is required")
    path = Path(p)
    if not path.is_absolute():
        path = Path(config["workspace"]) / path
    path = path.resolve()
    for root in allowed_roots():
        if path == Path(root).resolve() or path.is_relative_to(Path(root).resolve()):
            return path
    raise ToolError(f"Access denied: {path} is outside the allowed folders {allowed_roots()}")


def truncate(s: str, n=MAX_OUT) -> str:
    return s if len(s) <= n else s[:n] + f"\n... [truncated {len(s) - n} chars]"


# ---------------- file helpers ----------------
def extract_pdf_text(path: Path, max_chars=60_000) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages):
        parts.append(f"--- page {i + 1} ---\n{page.extract_text() or ''}")
        if sum(map(len, parts)) > max_chars:
            break
    return truncate("\n".join(parts), max_chars)


def list_dir(path: str) -> dict:
    p = resolve_path(path)
    if not p.is_dir():
        raise ToolError(f"Not a directory: {p}")
    entries = []
    for e in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:1000]:
        try:
            st = e.stat()
            entries.append({"name": e.name, "path": str(e), "is_dir": e.is_dir(),
                            "size": st.st_size if e.is_file() else 0, "modified": st.st_mtime})
        except OSError:
            continue
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "entries": entries}


def read_file(path: str, max_chars: int = 40_000) -> str:
    p = resolve_path(path)
    if not p.is_file():
        raise ToolError(f"Not a file: {p}")
    if p.suffix.lower() == ".pdf":
        return extract_pdf_text(p, max_chars)
    data = p.read_bytes()[: max_chars * 4]
    if b"\x00" in data[:4096] and p.suffix.lower() not in TEXT_EXT:
        return f"[binary file, {p.stat().st_size} bytes]"
    return truncate(data.decode("utf-8", errors="replace"), max_chars)


def write_file(path: str, content: str) -> str:
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {p}"


def search_files(root: str, pattern: str) -> str:
    p = resolve_path(root)
    hits = []
    for i, f in enumerate(p.rglob(pattern)):
        hits.append(str(f))
        if len(hits) >= 200:
            hits.append("... (limit reached)")
            break
    return "\n".join(hits) or "No matches."


# ---------------- images / files shown in the chat ----------------
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def share_file(path: Path) -> dict:
    """Copy a file into uploads and register it as an attachment the phone can display/download."""
    import mimetypes
    import shutil
    from .config import DATA_DIR
    dest = DATA_DIR / "uploads" / f"{uuid.uuid4().hex[:8]}_{path.name}"
    shutil.copy2(path, dest)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    kind = "image" if path.suffix.lower() in IMAGE_EXT else ("pdf" if path.suffix.lower() == ".pdf" else "file")
    a = db.add_attachment(path.name, mime, kind, str(dest), None, dest.stat().st_size)
    return {k: a[k] for k in ("id", "filename", "mime", "kind", "size")}


def take_screenshot() -> dict:
    """Capture all monitors of this PC and return it as an image attachment."""
    from PIL import ImageGrab
    from .config import DATA_DIR
    img = ImageGrab.grab(all_screens=True).convert("RGB")
    dest = DATA_DIR / "uploads" / f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    img.save(dest, "JPEG", quality=88)
    a = db.add_attachment(dest.name, "image/jpeg", "image", str(dest), None, dest.stat().st_size)
    return {k: a[k] for k in ("id", "filename", "mime", "kind", "size")}


def _recent_images(root: Path, since: float, limit=6) -> list[Path]:
    hits = []
    for p in root.rglob("*"):
        if ".runs" in p.parts or p.suffix.lower() not in IMAGE_EXT:
            continue
        try:
            if p.stat().st_mtime >= since:
                hits.append(p)
        except OSError:
            pass
    return sorted(hits, key=lambda p: p.stat().st_mtime)[-limit:]


# ---------------- web ----------------
def web_search(query: str, max_results: int = 6) -> str:
    from ddgs import DDGS
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception:  # search backends fail intermittently; one retry usually works
        time.sleep(1.5)
        results = DDGS().text(query, max_results=max_results)
    if not results:
        return "No results."
    return "\n\n".join(f"[{i + 1}] {r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')}"
                       for i, r in enumerate(results))


def _public_host(host: str) -> bool:
    """Block localhost / LAN / link-local targets so web pages can't be used to probe this PC or network."""
    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def fetch_url(url: str, max_chars: int = 20_000) -> str:
    import html as htmllib
    import re
    from urllib.parse import urlparse
    import httpx
    for _ in range(5):  # follow redirects manually so every hop is checked
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ToolError("Only http(s) URLs are allowed")
        if not _public_host(u.hostname):
            raise ToolError("Blocked: URL points to this PC or a private network")
        r = httpx.get(url, timeout=20, follow_redirects=False,
                      headers={"User-Agent": "Mozilla/5.0 (LocalAI Bridge)"})
        if r.is_redirect and r.headers.get("location"):
            url = str(r.url.join(r.headers["location"]))
            continue
        break
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype:
        return "[PDF document - ask the user to download it, or use run_code to process it]"
    text = r.text
    if "html" in ctype or text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        text = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", text)
        text = htmllib.unescape(re.sub(r"<[^>]+>", " ", text))
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return truncate(f"URL: {r.url}\n\n{text}", max_chars)


# ---------------- code execution ----------------
def run_code(language: str, code: str, timeout: int | None = None) -> dict:
    if not config["enable_code_exec"]:
        raise ToolError("Code execution is disabled in server config.")
    timeout = timeout or config["exec_timeout_sec"]
    ws = Path(config["workspace"])
    runs = ws / ".runs"
    runs.mkdir(parents=True, exist_ok=True)
    lang = language.lower()
    ext = {"python": ".py", "powershell": ".ps1", "cmd": ".bat"}.get(lang)
    if not ext:
        raise ToolError("language must be python, powershell or cmd")
    script = runs / f"run_{uuid.uuid4().hex[:8]}{ext}"
    script.write_text(code, encoding="utf-8-sig" if lang == "powershell" else "utf-8")
    cmd = {
        "python": [sys.executable, "-X", "utf8", str(script)],
        "powershell": ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        "cmd": ["cmd", "/c", str(script)],
    }[lang]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(cmd, cwd=ws, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW)
    with _procs_lock:
        PROCS[proc.pid] = {"pid": proc.pid, "language": lang, "session": current_session.get(),
                           "preview": code.strip().splitlines()[0][:80] if code.strip() else "", "started": time.time()}
    try:
        out, err = proc.communicate(timeout=timeout)
        code_ = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        out, err = proc.communicate()
        code_, timed_out = -1, True
    finally:
        script.unlink(missing_ok=True)
        with _procs_lock:
            info = PROCS.pop(proc.pid, None)
    if info and info.get("killed"):
        err = (err or b"") + b"\n[stopped by the user from the app]"
    dec = lambda b: b.decode("utf-8", errors="replace")
    return {"exit_code": code_, "timed_out": timed_out,
            "stdout": truncate(dec(out)), "stderr": truncate(dec(err), 8000)}


# ---------------- LLM tool schema ----------------
def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


def tool_schemas(web: bool = False):
    s = [
        _fn("list_dir", "List files and folders in a directory on the user's PC.",
            {"path": {"type": "string", "description": "Absolute path, or relative to the workspace"}}, ["path"]),
        _fn("read_file", "Read a text or PDF file from the user's PC.",
            {"path": {"type": "string"}}, ["path"]),
        _fn("search_files", "Recursively find files matching a glob pattern (e.g. '*.pdf').",
            {"root": {"type": "string"}, "pattern": {"type": "string"}}, ["root", "pattern"]),
        _fn("write_file", "Create or overwrite a text file on the user's PC.",
            {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
        _fn("take_screenshot", "Take a screenshot of the user's PC screen and show it in the chat.", {}, []),
        _fn("send_file_to_user", "Show an image (chart, figure, photo) or send any file from the PC to the "
            "user's phone chat. Images are displayed inline.",
            {"path": {"type": "string"}}, ["path"]),
        _fn("save_memory", "Save a durable fact or preference about the user for future sessions.",
            {"content": {"type": "string"}}, ["content"]),
        _fn("search_memory", "Search saved long-term memories.",
            {"query": {"type": "string"}}, ["query"]),
    ]
    if config["enable_code_exec"]:
        s.insert(0, _fn("run_code",
                        f"Execute code on the user's Windows PC. Working directory: {config['workspace']}. "
                        "Returns stdout, stderr and exit code. Use print() to show results. "
                        "Any image file the code saves (e.g. plt.savefig('chart.png')) is shown to the user "
                        "automatically - never call plt.show().",
                        {"language": {"type": "string", "enum": ["python", "powershell", "cmd"]},
                         "code": {"type": "string"}}, ["language", "code"]))
    if web:
        s += [
            _fn("web_search", "Search the internet (DuckDuckGo). Returns titles, URLs and snippets. "
                "Use for current events, facts you are unsure about, documentation, prices, etc.",
                {"query": {"type": "string"}}, ["query"]),
            _fn("fetch_url", "Download a web page and return its readable text. Use after web_search to read a result.",
                {"url": {"type": "string"}}, ["url"]),
        ]
    return s


NEEDS_APPROVAL = {"run_code", "write_file"}


def execute_tool(name: str, args: dict) -> tuple[str, list[dict]]:
    """Run a tool synchronously; returns (text for the LLM, attachments shown to the user)."""
    try:
        if name == "run_code":
            start = time.time() - 1
            r = run_code(args.get("language", "python"), args.get("code", ""))
            atts = [share_file(p) for p in _recent_images(Path(config["workspace"]), start)]
            if atts:
                r["images_displayed_to_user"] = [a["filename"] for a in atts]
                r["note"] = "These images are shown to the user; you cannot see them, so don't describe their content."
            return json.dumps(r, ensure_ascii=False), atts
        if name == "take_screenshot":
            a = take_screenshot()
            return (f"Screenshot taken and displayed to the user ({a['filename']}). You cannot see its "
                    "contents - do not describe it. The user can attach it to a message if you need to look."), [a]
        if name == "send_file_to_user":
            p = resolve_path(args.get("path", ""))
            if not p.is_file():
                raise ToolError(f"Not a file: {p}")
            a = share_file(p)
            return f"Sent {p.name} to the user (displayed in their chat).", [a]
        return _execute_text_tool(name, args), []
    except ToolError as e:
        return f"Error: {e}", []
    except Exception as e:  # report, don't crash the chat
        return f"Error: {type(e).__name__}: {e}", []


def _execute_text_tool(name: str, args: dict) -> str:
    try:
        if name == "list_dir":
            r = list_dir(args.get("path", ""))
            lines = [("[DIR] " if e["is_dir"] else f"{e['size']:>10}  ") + e["name"] for e in r["entries"]]
            return truncate(f"{r['path']}\n" + "\n".join(lines))
        if name == "read_file":
            return read_file(args.get("path", ""))
        if name == "web_search":
            return web_search(args.get("query", ""))
        if name == "fetch_url":
            return fetch_url(args.get("url", ""))
        if name == "search_files":
            return search_files(args.get("root", ""), args.get("pattern", "*"))
        if name == "write_file":
            return write_file(args.get("path", ""), args.get("content", ""))
        if name == "save_memory":
            mid = db.add_memory(args.get("content", ""))
            return f"Saved memory #{mid}"
        if name == "search_memory":
            hits = db.search_memories(args.get("query", ""))
            return "\n".join(f"#{m['id']}: {m['content']}" for m in hits) or "No matching memories."
        return f"Unknown tool: {name}"
    except ToolError as e:
        return f"Error: {e}"
    except Exception as e:  # report, don't crash the chat
        return f"Error: {type(e).__name__}: {e}"
