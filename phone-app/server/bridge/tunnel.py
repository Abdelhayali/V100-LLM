"""Starts cloudflared and captures the public tunnel URL."""
import ctypes
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

import psutil

from .config import DATA_DIR, SERVER_DIR, config

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"


def find_cloudflared(log=print) -> str:
    candidates = [config["cloudflared_path"], shutil.which("cloudflared"),
                  r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                  r"C:\Program Files\cloudflared\cloudflared.exe",
                  str(SERVER_DIR / "bin" / "cloudflared.exe")]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    target = SERVER_DIR / "bin" / "cloudflared.exe"
    target.parent.mkdir(exist_ok=True)
    log(f"cloudflared not found - downloading official build from GitHub to {target} ...")
    urllib.request.urlretrieve(DOWNLOAD_URL, target)
    return str(target)


def kill_stale_tunnels(port: int, log=print):
    """Kill cloudflared processes left over from earlier runs that point at our port."""
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower().startswith("cloudflared") and \
                    f"127.0.0.1:{port}" in " ".join(p.info["cmdline"] or []):
                p.kill()
                log(f"Stopped leftover cloudflared (pid {p.pid}).")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


class _KillOnCloseJob:
    """Windows job object: child processes die automatically when this app exits, even if killed."""

    def __init__(self):
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32 = k32
        self.handle = k32.CreateJobObjectW(None, None)

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]

        class EXT(ctypes.Structure):
            _fields_ = [("Basic", BASIC), ("Io", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        info = EXT()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        k32.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info))

    def add(self, proc: subprocess.Popen):
        self.k32.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(proc._handle)))


try:
    _job = _KillOnCloseJob()
except Exception:
    _job = None


class Tunnel:
    def __init__(self, port: int, on_url=None, log=print):
        self.port, self.on_url, self.log = port, on_url, log
        self.proc: subprocess.Popen | None = None
        self.url: str | None = None

    def start(self):
        mode = config["tunnel_mode"]
        if mode == "off":
            return
        kill_stale_tunnels(self.port, self.log)
        exe = find_cloudflared(self.log)
        if mode == "named":
            if not config["tunnel_token"]:
                self.log("tunnel_mode is 'named' but tunnel_token is empty in config.json")
                return
            cmd = [exe, "tunnel", "--no-autoupdate", "run", "--token", config["tunnel_token"]]
        else:
            cmd = [exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}"]
        self.log("Starting Cloudflare tunnel (takes 5-20 s) ...")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace",
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        if _job:
            try:
                _job.add(self.proc)
            except Exception:
                pass
        if mode == "named" and config["public_url"]:
            self._set_url(config["public_url"].rstrip("/"))
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._watchdog, daemon=True).start()

    def _set_url(self, url):
        self.url = url
        (DATA_DIR / "tunnel_url.txt").write_text(url, encoding="utf-8")
        if self.on_url:
            self.on_url(url)

    def _reader(self):
        with open(DATA_DIR / "cloudflared.log", "w", encoding="utf-8") as logf:
            for line in self.proc.stdout:
                line = line.rstrip()
                logf.write(line + "\n")
                logf.flush()
                if not self.url:
                    m = URL_RE.search(line)
                    if m:
                        self._set_url(m.group(0))
                if " ERR " in line or "failed" in line.lower():
                    self.log("[cloudflared] " + line[-200:])
        self.log(f"cloudflared exited (code {self.proc.poll()}). See server/data/cloudflared.log")

    def _watchdog(self):
        time.sleep(45)
        if not self.url and self.proc and self.proc.poll() is None:
            self.log("Still waiting for the tunnel URL... check your internet connection, "
                     "or see server/data/cloudflared.log")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.url = None
