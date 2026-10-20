"""LocalAI Bridge Desktop: the phone app's features for Windows laptops, in an app window.

The window (Microsoft Edge in app mode, built into Windows 10/11) shows the UI in ui/. This program serves it on
127.0.0.1 and forwards /api/* to the LocalAI Bridge server (on this PC or through its tunnel) with the access token,
so the token never reaches the page and there are no cross-origin problems. A random key, given to the window at
start (cookie), stops other programs and web pages on this PC from using the proxy.
"""
import base64
import http.client
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = "LocalAI Bridge Desktop"
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
UI = HERE / "ui"
CFG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP
CFG = CFG_DIR / "settings.json"
LOCK = CFG_DIR / "running.json"
KEY = secrets.token_urlsafe(24)
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json"}


def load() -> dict:
    try:
        return json.loads(CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(d: dict):
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps(d, indent=1), encoding="utf-8")


settings = load()


def _conn(url: str, timeout=900):
    u = urllib.parse.urlsplit(url)
    if u.scheme == "https":
        return http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=timeout, context=ssl.create_default_context()), u
    return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout), u


def check(url: str, token: str) -> dict:
    """GET /api/info on a server: returns its info or raises with a readable reason."""
    c, u = _conn(url.rstrip("/"), timeout=20)
    try:
        c.request("GET", (u.path.rstrip("/") or "") + "/api/info", headers={"Authorization": "Bearer " + token})
        r = c.getresponse()
        body = r.read().decode("utf-8", "replace")
        if r.status == 401:
            raise ValueError("The token is wrong (the server refused it)")
        if r.status != 200:
            raise ValueError(f"The server answered HTTP {r.status}")
        return json.loads(body)
    except (OSError, http.client.HTTPException) as e:
        raise ValueError(f"Cannot reach {url}: {e}")
    finally:
        c.close()


def local_servers() -> list[dict]:
    """LocalAI Bridge servers configured on this PC (to connect without typing a token)."""
    here = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    cands = [here.parent / "server" / "config.json", here / "server" / "config.json",
             Path(r"D:\LocalAI-Bridge-V100\server\config.json"), Path(r"D:\V100-LLM\phone-app\server\config.json"),
             Path(r"D:\LocalAI-Bridge\server\config.json")]
    out, seen = [], set()
    for p in cands:
        try:
            c = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        url = f"http://127.0.0.1:{c.get('port', 8765)}"
        if url in seen or not c.get("auth_token"):
            continue
        seen.add(url)
        out.append({"url": url, "token": c["auth_token"], "path": str(p)})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # ---- guard: only our own window
    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def _authed(self) -> bool:
        cookie = self.headers.get("Cookie", "")
        return any(p.strip() == f"k={KEY}" for p in cookie.split(";"))

    def _send(self, code: int, body: bytes = b"", ctype: str = "application/json", extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj).encode())

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _route(self):
        if not self._host_ok():
            return self._send(403, b"forbidden host", "text/plain")
        path, _, query = self.path.partition("?")
        if path == "/" and f"k={KEY}" in query:          # first load of the window: hand it the key as a cookie
            return self._send(302, b"", extra={"Location": "/", "Set-Cookie": f"k={KEY}; HttpOnly; SameSite=Strict; Path=/"})
        if not self._authed():
            return self._send(403, b"Open LocalAI Bridge Desktop from its program, not from a browser.", "text/plain")
        if path.startswith("/api/"):
            return self._proxy()
        if path.startswith("/local/"):
            return self._local(path)
        f = (UI / ("index.html" if path in ("", "/") else path.lstrip("/"))).resolve()
        if UI.resolve() not in f.parents and f != UI.resolve() or not f.is_file():
            return self._send(404, b"not found", "text/plain")
        self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _route

    # ---- this app's own settings
    def _local(self, path: str):
        global settings
        if path == "/local/settings":
            return self._json(200, {"paired": bool(settings.get("url") and settings.get("token")), "url": settings.get("url", ""),
                                    "prefs": settings.get("prefs", {}), "local": [{"url": s["url"]} for s in local_servers()]})
        if path == "/local/prefs" and self.command == "POST":
            settings["prefs"] = json.loads(self._body() or b"{}")
            save(settings)
            return self._json(200, {"ok": True})
        if path == "/local/pair" and self.command == "POST":
            d = json.loads(self._body() or b"{}")
            url, token = (d.get("url") or "").strip().rstrip("/"), (d.get("token") or "").strip()
            code = (d.get("code") or "").strip()
            if code:          # the QR text {"url":..,"token":..}, raw or base64
                try:
                    j = json.loads(code if code.startswith("{") else base64.b64decode(code + "==").decode())
                    url, token = j["url"].rstrip("/"), j["token"]
                except Exception:
                    return self._json(400, {"error": "That pairing code is not valid"})
            if d.get("local"):
                ls = local_servers()
                if not ls:
                    return self._json(400, {"error": "No LocalAI Bridge server found on this PC"})
                url, token = ls[0]["url"], ls[0]["token"]
            if not url or not token:
                return self._json(400, {"error": "Enter the server URL and the access token"})
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            try:
                info = check(url, token)
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            settings.update(url=url, token=token)
            save(settings)
            return self._json(200, {"ok": True, "url": url, "models": info.get("models", [])})
        if path == "/local/unpair" and self.command == "POST":
            settings.pop("token", None)
            save(settings)
            return self._json(200, {"ok": True})
        self._json(404, {"error": "unknown"})

    # ---- forward to the LocalAI Bridge server, streaming (chat replies are Server-Sent Events)
    def _proxy(self):
        url, token = settings.get("url"), settings.get("token")
        if not url or not token:
            return self._json(428, {"detail": "Not connected to a LocalAI Bridge server"})
        body = self._body()
        try:
            c, u = _conn(url)
            hdr = {"Authorization": "Bearer " + token}
            for h in ("Content-Type", "Accept", "X-Vault-Key"):   # X-Vault-Key: the private vault, only while unlocked
                if self.headers.get(h):
                    hdr[h] = self.headers[h]
            c.request(self.command, (u.path.rstrip("/") or "") + self.path, body=body or None, headers=hdr)
            r = c.getresponse()
        except (OSError, http.client.HTTPException) as e:
            return self._json(502, {"detail": f"Server/tunnel offline ({e.__class__.__name__}). Is the PC server running?"})
        try:
            self.send_response(r.status)
            for h in ("Content-Type", "Content-Disposition", "Cache-Control"):
                if r.getheader(h):
                    self.send_header(h, r.getheader(h))
            n = r.getheader("Content-Length")
            if n:
                self.send_header("Content-Length", n)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = r.read1(16384)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass                       # the window closed the stream (e.g. switched chat)
        finally:
            c.close()


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def edge_path() -> str | None:
    for p in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)") + r"\Microsoft\Edge\Application\msedge.exe",
              os.environ.get("ProgramFiles", r"C:\Program Files") + r"\Microsoft\Edge\Application\msedge.exe",
              shutil.which("msedge") or ""):
        if p and os.path.exists(p):
            return p
    return None


def open_window(url: str) -> subprocess.Popen | None:
    edge = edge_path()
    if not edge:
        webbrowser.open(url)
        return None
    prof = Path(os.environ.get("LOCALAPPDATA", str(CFG_DIR))) / APP / "window"
    return subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={prof}", "--no-first-run", "--no-default-browser-check",
                             "--disable-features=Translate", "--window-size=1440,920"])


def already_running() -> bool:
    """A second start just opens another window of the running app."""
    try:
        d = json.loads(LOCK.read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", d["port"]), timeout=1):
            pass
        open_window(f"http://127.0.0.1:{d['port']}/?k={d['key']}")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    if "--no-window" not in sys.argv and already_running():
        sys.exit(0)
    PORT = free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    LOCK.write_text(json.dumps({"port": PORT, "key": KEY, "pid": os.getpid()}), encoding="utf-8")
    if "--no-window" in sys.argv:          # for testing: print the address instead of opening the window
        print(f"http://127.0.0.1:{PORT}/?k={KEY}", flush=True)
        proc = None
    else:
        proc = open_window(f"http://127.0.0.1:{PORT}/?k={KEY}")
    try:
        if proc:
            proc.wait()           # the app ends when its window is closed
            time.sleep(1.5)       # Edge may hand the window to a child process: stay while it lives
            while True:
                out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq msedge.exe", "/V", "/FO", "CSV"],
                                     capture_output=True, text=True, creationflags=0x08000000).stdout
                if APP not in out and "LocalAI Bridge" not in out:
                    break
                time.sleep(3)
        else:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass
        srv.shutdown()
