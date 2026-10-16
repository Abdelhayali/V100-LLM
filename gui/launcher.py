"""
V100-LLM launcher: pick a model, a preset and a kernel (engine), download whatever is missing,
start/stop llama-server, watch VRAM and logs, chat (text + images) with a live tokens/s readout,
and write a standalone run-<preset>.bat for any configuration.

Layout (all paths relative to the V100-LLM folder, so the folder can be copied to any PC):
  catalog.json                 models, files (url + sha256), presets, kernels
  models/<id>/model/           model files
  models/<id>/kernel/<engine>/ engine binaries (hard-linked from _kernels/ when available)
  models/<id>/run-<preset>.bat standalone launch scripts
  _kernels/<engine>/           shared engine store (optional; filled by downloads)

Run:  START-GUI.bat   (or: python gui/launcher.py) then open http://127.0.0.1:7860
Standard library only.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUI = Path(__file__).resolve().parent
CATALOG = ROOT / "catalog.json"
USER_PARAMS = ROOT / "user-params.json"
UI_PORT = int(os.environ.get("LAUNCHER_PORT", "7860"))
HOST = "127.0.0.1"

state = {"proc": None, "model": None, "preset": None, "kernel": None, "port": None, "started": None, "cmd": None}
dl = {"active": False, "item": "", "done": 0, "total": 0, "error": "", "queue": []}
log = deque(maxlen=500)
lock = threading.Lock()


# ---------------------------------------------------------------- catalog / paths
def catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def model_entry(mid):
    return next(m for m in catalog()["models"] if m["id"] == mid)


def model_dir(mid):
    return ROOT / "models" / mid


def kernel_dir(mid, k):
    return model_dir(mid) / "kernel" / k


def kernel_exe(mid, k):
    return kernel_dir(mid, k) / catalog()["kernels"][k]["exe"]


def file_path(mid, name):
    return model_dir(mid) / "model" / Path(name)


def model_status(m):
    files = []
    for f in m["files"]:
        p = file_path(m["id"], f["name"])
        have = p.exists() and (f.get("size") is None or p.stat().st_size == f["size"])
        files.append({"name": f["name"], "size": f["size"], "have": have,
                      "partial": p.stat().st_size if p.exists() and not have else 0})
    kernels = {k: kernel_exe(m["id"], k).exists() or (ROOT / "_kernels" / k / catalog()["kernels"][k]["exe"]).exists()
               for k in {k for p in m["presets"] for k in p.get("kernels", [p["kernel"]])}}
    return {"files": files, "kernels": kernels}


def resolve(mid, value):
    """{model:<file>} placeholders -> absolute path of that model file."""
    v = str(value)
    while "{model:" in v:
        a = v.index("{model:")
        b = v.index("}", a)
        v = v[:a] + str(file_path(mid, v[a + 7:b])) + v[b + 1:]
    return v


def is_strata(k):
    return catalog()["kernels"][k].get("type") == "strata"


def strata_config(mid, k, params, port):
    """Strata runs behind its own Python server; write its engine config with this folder's paths."""
    m = model_entry(mid)
    s = m["strata"]
    kd, md = kernel_dir(mid, k), model_dir(mid) / "model"
    args = []
    for p in params:
        if not p.get("on", True) or not p.get("flag"):
            continue
        args.append(p["flag"])
        v = str(p.get("value", "")).strip()
        if v != "":
            args.append(resolve(mid, v).replace("{kernel}", str(kd)))
    eng = kd / catalog()["kernels"][k]["exe"]
    cfg = {"exe": str(eng), "args": args, "cwd": str(kd), "tokenizer": str(md / s["tokenizer"]),
           "model_name": s["model_name"], "log": str(model_dir(mid) / "strata.log"), "lib_dirs": [str(eng.parent)],
           "port": port, "cuda": 12, "gpu": 0, "gpus_asked": True, "open_browser": False}
    if "--vision" in args and s.get("vision"):
        v = dict(s["vision"])
        v["exe"] = str(eng.parent / v["exe"])
        v["mmproj"] = str(md / v["mmproj"])
        v["model"] = str(md / v["model"])
        cfg["vision"] = v
    out = kd / "v100-llm-config.json"
    out.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    return [sys.executable, str(kd / "serve" / "server.py"), "--engine", "strata", "--config", str(out)]


def is_tabby(k):
    return catalog()["kernels"][k].get("type") == "tabby"


def tabby_config(mid, k, params, port):
    """ExLlamaV3 runs behind TabbyAPI: write its config.yml from the editable parameters (key -> value)."""
    kd = kernel_dir(mid, k)
    sample = (kd / "tabbyAPI" / "config_sample.yml").read_text(encoding="utf-8")
    sets = {"host": HOST, "port": str(port), "disable_auth": "true", "backend": "exllamav3",
            "model_dir": str(model_dir(mid)).replace("\\", "/"), "model_name": "model"}
    for p in params:
        if p.get("on", True) and p.get("flag"):
            sets[p["flag"].lstrip("-").replace("-", "_")] = str(p.get("value", "")).strip() or "true"
    import re as _re
    for key, val in sets.items():
        sample, _n = _re.subn(rf"(?m)^(\s*){_re.escape(key)}:.*$", rf"\g<1>{key}: {val}", sample, count=1)
    (kd / "tabbyAPI" / "config.yml").write_text(sample, encoding="utf-8")
    return [str(kd / "venv" / "Scripts" / "python.exe"), str(kd / "tabbyAPI" / "main.py")]


def build_cmd(mid, k, params):
    m = model_entry(mid)
    cmd = [str(kernel_exe(mid, k)), "-m", str(file_path(mid, m["model"]))]
    if m.get("mmproj") and file_path(mid, m["mmproj"]).exists():
        cmd += ["--mmproj", str(file_path(mid, m["mmproj"]))]
    for p in params:
        if not p.get("on", True) or not p.get("flag"):
            continue
        cmd.append(p["flag"])
        v = str(p.get("value", "")).strip()
        if v != "":
            cmd.append(resolve(mid, v))
    return cmd


# ---------------------------------------------------------------- downloads
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(url, dest, size=None):
    """Resumable download with progress in dl{}."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = dest.stat().st_size if dest.exists() else 0
    if size and have == size:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "V100-LLM", **({"Range": f"bytes={have}-"} if have else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206:
            have = 0
        total = have + int(r.headers.get("Content-Length", 0))
        dl.update(done=have, total=size or total)
        with open(dest, "ab" if have else "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                dl["done"] += len(b)


def ensure_kernel(mid, k):
    """Kernel present in models/<id>/kernel/<k>? else hard-link from _kernels/<k>, else download and unpack."""
    kd = kernel_dir(mid, k)
    exe = catalog()["kernels"][k]["exe"]
    if (kd / exe).exists():
        return
    store = ROOT / "_kernels" / k
    if not (store / exe).exists():
        tmp = Path(tempfile.mkdtemp(prefix="v100llm-"))
        try:
            for i, d in enumerate(catalog()["kernels"][k]["download"]):
                dl["item"] = f"kernel {k} ({i + 1}/{len(catalog()['kernels'][k]['download'])})"
                z = tmp / f"k{i}.zip"
                fetch(d["url"], z)
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(tmp / "x")
            # the zip may contain a top folder; the kernel root is where <exe> (which may include a sub-path) sits
            rel_exe = Path(exe)
            exe_path = next(p for p in (tmp / "x").rglob(rel_exe.name) if p.as_posix().endswith(rel_exe.as_posix()))
            src = exe_path.parents[len(rel_exe.parts) - 1]
            store.mkdir(parents=True, exist_ok=True)
            for f in (tmp / "x").rglob("*"):
                if not f.is_file():
                    continue
                rel = f.relative_to(src) if src in f.parents else Path(f.name)   # stray DLLs go to the root
                t = store / rel
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), t)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    for f in store.rglob("*"):
        if f.is_file():
            t = kd / f.relative_to(store)
            if not t.exists():
                t.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(f, t)          # hard link: no extra disk space
                except OSError:
                    shutil.copy2(f, t)     # other drive / FAT: plain copy


def download_worker(mid, k):
    m = model_entry(mid)
    try:
        dl.update(active=True, error="")
        if k:
            ensure_kernel(mid, k)
        if m.get("setup"):
            # models prepared by their own engine's setup (Strata: download GGUFs, build packs)
            dl.update(item=f"{m['name']}: running the engine's setup (download + prepare, can take an hour)", done=0, total=0)
            env = dict(os.environ, **m["setup"].get("env", {}))
            kd = kernel_dir(mid, k or m["presets"][0]["kernel"])
            cmd = [sys.executable if a == "{python}" else a.replace("{kernel}", str(kd)).replace("{model}", str(model_dir(mid) / "model"))
                   for a in m["setup"]["cmd"]]
            with open(model_dir(mid) / "setup.log", "w", encoding="utf-8", errors="replace") as lf:
                rc = subprocess.run(cmd, cwd=kd, env=env, stdout=lf, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode
            if rc:
                raise RuntimeError(f"setup failed (exit {rc}); see {model_dir(mid) / 'setup.log'}")
            dl["item"] = "done"
            return
        for f in m["files"]:
            p = file_path(mid, f["name"])
            if p.exists() and p.stat().st_size == f["size"]:
                continue
            dl["item"] = f["name"]
            fetch(f["url"], p, f["size"])
            dl["item"] = f"verifying {f['name']}"
            if sha256(p) != f["sha256"]:
                p.unlink()
                raise RuntimeError(f"checksum mismatch for {f['name']} (deleted, download again)")
        dl["item"] = "done"
    except Exception as e:
        dl["error"] = str(e)
    finally:
        dl["active"] = False


# ---------------------------------------------------------------- server control
def reader(proc):
    for line in iter(proc.stdout.readline, ""):
        log.append(line.rstrip())
    log.append(f"[launcher] server exited with code {proc.wait()}")


def stop_server():
    with lock:
        p = state["proc"]
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        state.update(proc=None, model=None, preset=None, kernel=None, started=None, cmd=None)


def start_server(mid, preset, k, params):
    m = model_entry(mid)
    missing = [f["name"] for f in m["files"] if not file_path(mid, f["name"]).exists()]
    if missing:
        raise FileNotFoundError("missing model files: " + ", ".join(missing) + " - press Download")
    if not kernel_exe(mid, k).exists():
        ensure_kernel(mid, k) if (ROOT / "_kernels" / k).exists() else None
        if not kernel_exe(mid, k).exists():
            raise FileNotFoundError(f"kernel '{k}' not installed - press Download")
    stop_server()
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    time.sleep(2)
    port = catalog().get("server_port", 8899)
    if is_strata(k):
        cmd = strata_config(mid, k, params, port) + ["--port", str(port)]
    elif is_tabby(k):
        cmd = tabby_config(mid, k, params, port)
    else:
        cmd = build_cmd(mid, k, params) + ["--host", HOST, "--port", str(port)]
    env = dict(os.environ)
    env["PATH"] = str(kernel_dir(mid, k)) + os.pathsep + str(kernel_dir(mid, k) / "cuda") + os.pathsep + env.get("PATH", "")
    log.clear()
    log.append("[launcher] " + subprocess.list2cmdline(cmd))
    proc = subprocess.Popen(cmd, cwd=kernel_dir(mid, k) / "tabbyAPI" if is_tabby(k) else kernel_dir(mid, k), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    threading.Thread(target=reader, args=(proc,), daemon=True).start()
    with lock:
        state.update(proc=proc, model=mid, preset=preset, kernel=k, port=port, started=time.time(), cmd=cmd)
    saved = load_user()
    saved[f"{mid}/{preset}/{k}"] = params
    USER_PARAMS.write_text(json.dumps(saved, indent=1), encoding="utf-8")


def load_user():
    try:
        return json.loads(USER_PARAMS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_bat(mid, preset, k, params, name=None):
    """Standalone launcher using paths relative to the .bat (works after copying the folder)."""
    m = model_entry(mid)
    pre = next((p for p in m["presets"] if p["id"] == preset), None)
    lines = ["@echo off", f"rem {m['name']} - {pre['name'] if pre else preset} (kernel: {k})",
             f"rem {pre.get('bench', '') if pre else ''}".rstrip(),
             "rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.",
             'if not defined PORT set "PORT=8899"', 'if not defined HOST set "HOST=127.0.0.1"',
             f'set "K=%~dp0kernel\\{k}"', 'set "M=%~dp0model"', 'set "PATH=%K%;%PATH%"',
             f'if not exist "%K%\\{catalog()["kernels"][k]["exe"]}" ( echo Kernel {k} missing: open START-GUI.bat and press Download. & pause & exit /b 1 )',
             f'"%K%\\{catalog()["kernels"][k]["exe"]}" ^', f'  -m "%M%\\{m["model"]}" ^']
    if m.get("mmproj"):
        lines.append(f'  --mmproj "%M%\\{m["mmproj"]}" ^')
    for p in params:
        if not p.get("on", True) or not p.get("flag"):
            continue
        v = str(p.get("value", "")).strip()
        while "{model:" in v:
            a = v.index("{model:"); b = v.index("}", a)
            v = v[:a] + "%M%\\" + v[a + 7:b] + v[b + 1:]
        lines.append(f'  {p["flag"]} {chr(34) + v + chr(34) if " " in v or "%M%" in v else v} ^'.rstrip() if v else f'  {p["flag"]} ^')
    lines += ["  --host %HOST% --port %PORT% %*", "if errorlevel 1 pause"]
    if is_strata(k):
        # Strata runs behind its Python server: let the launcher write its config and run it in this window
        lines = ["@echo off", f"rem {m['name']} - {pre['name'] if pre else preset} (kernel: strata)",
                 "rem Open http://127.0.0.1:%PORT% (default 8899).",
                 f'"%~dp0..\\..\\runtime\\python\\python.exe" "%~dp0..\\..\\gui\\launcher.py" --serve {mid}:{preset}',
                 "if errorlevel 1 pause"]
    out = model_dir(mid) / (name or f"run-{preset}.bat")
    with open(out, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    return out


def server_health():
    if not state["proc"] or state["proc"].poll() is not None:
        return "stopped"
    try:
        with urllib.request.urlopen(f"http://{HOST}:{state['port']}/health", timeout=2) as r:
            return "ready" if json.loads(r.read()).get("status") in ("ok", "healthy") else "loading"
    except urllib.error.HTTPError as e:
        return "loading" if e.code == 503 else "error"
    except Exception:
        return "loading"


def gpu_info():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout
        name, used, total, util = [x.strip() for x in out.splitlines()[0].split(",")]
        return {"name": name, "used": int(used), "total": int(total), "util": int(util)}
    except Exception:
        return None


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/":
            b = (GUI / "ui.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif self.path == "/api/catalog":
            c = catalog()
            self.send_json({"catalog": c, "user": load_user(),
                            "status": {m["id"]: model_status(m) for m in c["models"]}})
        elif self.path == "/api/status":
            p = state["proc"]
            self.send_json({"model": state["model"], "preset": state["preset"], "kernel": state["kernel"],
                            "health": server_health(), "port": state["port"],
                            "uptime": round(time.time() - state["started"]) if state["started"] else 0,
                            "gpu": gpu_info(), "log": list(log)[-150:], "download": dl,
                            "exit": p.poll() if p else None})
        else:
            self.send_error(404)

    def do_POST(self):
        try:
            if self.path == "/api/start":
                b = self.body()
                start_server(b["id"], b["preset"], b["kernel"], b["params"])
                self.send_json({"ok": True})
            elif self.path == "/api/stop":
                stop_server()
                self.send_json({"ok": True})
            elif self.path == "/api/download":
                b = self.body()
                if dl["active"]:
                    raise RuntimeError("a download is already running")
                threading.Thread(target=download_worker, args=(b["id"], b.get("kernel")), daemon=True).start()
                self.send_json({"ok": True})
            elif self.path == "/api/bat":
                b = self.body()
                out = write_bat(b["id"], b["preset"], b["kernel"], b["params"], b.get("name"))
                self.send_json({"ok": True, "path": str(out)})
            elif self.path == "/api/chat":
                self.proxy_chat()
            else:
                self.send_error(404)
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)}, 500)

    def proxy_chat(self):
        n = int(self.headers.get("Content-Length", 0))
        req = urllib.request.Request(f"http://{HOST}:{state['port']}/v1/chat/completions",
                                     data=self.rfile.read(n), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=7200) as r:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            while True:
                line = r.readline()
                if not line:
                    break
                self.wfile.write(line)
                self.wfile.flush()


def gen_all_bats():
    for m in catalog()["models"]:
        for p in m["presets"]:
            params = [{"flag": x[0], "value": x[1], "on": True} for x in p["params"]]
            print("wrote", write_bat(m["id"], p["id"], p["kernel"], params))


if __name__ == "__main__":
    if "--gen-bats" in sys.argv:
        gen_all_bats()
        sys.exit(0)
    if "--serve" in sys.argv:
        # run one preset in the foreground (used by Strata's run-*.bat)
        mid, _, pid = sys.argv[sys.argv.index("--serve") + 1].partition(":")
        m = model_entry(mid)
        p = next(x for x in m["presets"] if x["id"] == pid)
        params = [{"flag": x[0], "value": x[1], "on": True} for x in p["params"]]
        port = int(os.environ.get("PORT", catalog().get("server_port", 8899)))
        k = p["kernel"]
        cmd = strata_config(mid, k, params, port) + ["--port", str(port)] if is_strata(k) else \
            build_cmd(mid, k, params) + ["--host", HOST, "--port", str(port)]
        env = dict(os.environ, PATH=str(kernel_dir(mid, k)) + os.pathsep + os.environ.get("PATH", ""))
        sys.exit(subprocess.call(cmd, cwd=kernel_dir(mid, k), env=env))
    print(f"V100-LLM launcher: http://{HOST}:{UI_PORT}")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: os.startfile(f"http://{HOST}:{UI_PORT}") if hasattr(os, "startfile") else None).start()
    try:
        ThreadingHTTPServer((HOST, UI_PORT), Handler).serve_forever()
    finally:
        stop_server()
