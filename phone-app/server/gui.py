"""Windows control panel: start/stop the server, show the Cloudflare URL + pairing QR."""
import ctypes
import os
import queue
import sys
import threading
import traceback
from pathlib import Path

# pythonw.exe has no console: send stray output to a log file instead of crashing on None streams
_LOG_DIR = Path(__file__).resolve().parent / "data"
_LOG_DIR.mkdir(exist_ok=True)
if sys.stdout is None or sys.stderr is None:
    _f = open(_LOG_DIR / "gui.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _f
    sys.stderr = sys.stderr or _f

import tkinter as tk  # noqa: E402
from tkinter import messagebox, ttk  # noqa: E402

import httpx  # noqa: E402
import qrcode  # noqa: E402
from PIL import ImageTk  # noqa: E402

try:
    from bridge.config import CONFIG_PATH, config, llm_api_base
    from bridge.runner import BridgeServer
except Exception as _e:  # e.g. a typo in config.json - show it instead of dying silently
    traceback.print_exc()
    _r = tk.Tk()
    _r.withdraw()
    messagebox.showerror("LocalAI Bridge - startup error",
                         f"{type(_e).__name__}: {_e}\n\nIf this mentions config.json, fix or delete "
                         "server\\config.json (it is recreated with defaults).")
    sys.exit(1)

AUTO_MODEL = "(auto - first available)"


def single_instance() -> bool:
    """Named mutex: only one control panel at a time."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\LocalAIBridgeGUI")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.srv = BridgeServer(log=lambda m: self.q.put(("log", m)),
                                on_url=lambda u: self.q.put(("url", u)))
        root.title("LocalAI Bridge Server")
        root.geometry("1000x680")
        root.minsize(780, 580)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.report_callback_exception = lambda *a: self.write_log("".join(traceback.format_exception(*a)))

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")
        self.status = tk.StringVar(value="Stopped")
        ttk.Label(top, text="Status:", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.status_lbl = ttk.Label(top, textvariable=self.status, foreground="#b00", font=("Segoe UI", 11))
        self.status_lbl.pack(side="left", padx=6)
        self.btn = ttk.Button(top, text="Start server", command=self.toggle)
        self.btn.pack(side="right")

        body = ttk.Frame(root, padding=(10, 0))
        body.pack(fill="both", expand=True)
        right = ttk.Frame(body, padding=(10, 0))  # packed first so the QR always keeps its space
        right.pack(side="right", fill="y")
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)

        # --- connection
        conn = ttk.LabelFrame(left, text="Connection", padding=8)
        conn.pack(fill="x")
        self.url = tk.StringVar(value="(start the server)")
        self._row(conn, 0, "Public URL", self.url, copy=True)
        self.token = tk.StringVar(value=config["auth_token"])
        self.show_tok = tk.BooleanVar(value=False)
        self.tok_entry = self._row(conn, 1, "Access token", self.token, copy=True, secret=True)
        ttk.Checkbutton(conn, text="Show", variable=self.show_tok,
                        command=lambda: self.tok_entry.config(show="" if self.show_tok.get() else "•")
                        ).grid(row=1, column=3, padx=2)
        ttk.Button(conn, text="New token", command=self.new_token).grid(row=1, column=4)

        # --- local LLM
        st = ttk.LabelFrame(left, text="Local LLM", padding=8)
        st.pack(fill="x", pady=8)
        st.columnconfigure(1, weight=1)
        self.llm_url = tk.StringVar(value=config["llm_base_url"])
        ttk.Label(st, text="LLM server URL").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(st, textvariable=self.llm_url).grid(row=0, column=1, sticky="we", pady=2)
        self.llm_state = ttk.Label(st, text="", width=14)
        self.llm_state.grid(row=0, column=2, padx=6)

        ttk.Label(st, text="Default model").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        self.model = tk.StringVar(value=config["default_model"] or AUTO_MODEL)
        self.model_box = ttk.Combobox(st, textvariable=self.model, values=[AUTO_MODEL])
        self.model_box.grid(row=1, column=1, sticky="we", pady=2)
        ttk.Button(st, text="Refresh models", command=self.fetch_models).grid(row=1, column=2, padx=6)
        ttk.Label(st, text="llama.cpp http://127.0.0.1:8080  •  Ollama http://127.0.0.1:11434  •  "
                           "LM Studio http://127.0.0.1:1234   (no API key needed)",
                  foreground="#666").grid(row=2, column=1, columnspan=2, sticky="w")
        self.approve = tk.BooleanVar(value=config["require_tool_approval"])
        self.exec_on = tk.BooleanVar(value=config["enable_code_exec"])
        flags = ttk.Frame(st)
        flags.grid(row=3, column=1, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Checkbutton(flags, text="Allow code execution", variable=self.exec_on).pack(side="left")
        ttk.Checkbutton(flags, text="Phone must approve code/file writes", variable=self.approve).pack(side="left", padx=12)
        bar = ttk.Frame(st)
        bar.grid(row=4, column=1, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(bar, text="Save settings", command=self.save).pack(side="left")
        ttk.Button(bar, text="Open config.json (folders, tunnel...)",
                   command=lambda: os.startfile(CONFIG_PATH)).pack(side="left", padx=6)

        # --- log
        lg = ttk.LabelFrame(left, text="Log", padding=4)
        lg.pack(fill="both", expand=True, pady=(0, 10))
        self.log = tk.Text(lg, height=10, font=("Consolas", 9), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

        # --- QR
        ttk.Label(right, text="Scan in the Android app", font=("Segoe UI", 10, "bold")).pack()
        self.qr_lbl = ttk.Label(right, text="QR appears when the\ntunnel is ready", anchor="center", width=34)
        self.qr_lbl.pack(pady=6)
        ttk.Label(right, text="Keep this QR private:\nit grants access to this PC.", foreground="#a00",
                  justify="center").pack()

        root.after(100, self.pump)
        root.after(1500, self.watch)
        self.fetch_models()
        if "--autostart" in sys.argv:
            root.after(300, self.toggle)

    # ---------------------------------------------------------------- helpers
    def _row(self, parent, r, label, var, copy=False, secret=False):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0, 6), pady=2)
        e = ttk.Entry(parent, textvariable=var, width=52, show="•" if secret else "")
        e.state(["readonly"])
        e.grid(row=r, column=1, sticky="we", pady=2)
        parent.columnconfigure(1, weight=1)
        if copy:
            ttk.Button(parent, text="Copy", width=6, command=lambda: self.copy(var.get())).grid(row=r, column=2, padx=4)
        return e

    def copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.write_log("Copied to clipboard.")

    def write_log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def pump(self):
        while not self.q.empty():
            kind, val = self.q.get()
            if kind == "log":
                self.write_log(val)
            elif kind == "url":
                self.url.set(val)
                self.render_qr()
            elif kind == "models":
                ok, models, err = val
                self.model_box["values"] = [AUTO_MODEL] + models
                self.llm_state.config(text="● online" if ok else "● offline",
                                      foreground="#080" if ok else "#b00")
                if ok and self._models_manual:
                    self.write_log(f"Models: {', '.join(models) or 'none loaded'}")
                elif not ok and self._models_manual:
                    self.write_log(f"LLM server not reachable at {llm_api_base()}: {err}")
        self.root.after(150, self.pump)

    def watch(self):
        """Detect a server that died, and refresh the model list every 15 s."""
        if self.status.get() == "Running" and not self.srv.running:
            self.set_stopped()
            self.write_log("Server stopped unexpectedly. " + (self.srv.error or ""))
        self._tick = getattr(self, "_tick", 0) + 1
        if self._tick % 10 == 0:
            self.fetch_models(manual=False)
        self.root.after(1500, self.watch)

    # ---------------------------------------------------------------- models
    def fetch_models(self, manual=True):
        self._models_manual = manual
        config.data["llm_base_url"] = self.llm_url.get().strip() or config["llm_base_url"]
        base = llm_api_base()

        def work():
            try:
                r = httpx.get(base + "/models", timeout=4)
                r.raise_for_status()
                self.q.put(("models", (True, [m["id"] for m in r.json().get("data", [])], None)))
            except Exception as e:
                self.q.put(("models", (False, [], f"{type(e).__name__}")))

        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- actions
    def render_qr(self):
        img = qrcode.make(self.srv.pairing_payload(), box_size=6, border=2).get_image().resize((260, 260))
        self.qr_img = ImageTk.PhotoImage(img)
        self.qr_lbl.config(image=self.qr_img, text="")

    def set_stopped(self):
        self.status.set("Stopped")
        self.status_lbl.config(foreground="#b00")
        self.btn.config(text="Start server", state="normal")
        self.url.set("(start the server)")
        self.qr_lbl.config(image="", text="QR appears when the\ntunnel is ready")

    def toggle(self):
        if self.srv.running:
            self.srv.stop()
            self.set_stopped()
            return
        self.save(quiet=True)
        self.status.set("Starting…")
        self.status_lbl.config(foreground="#a60")
        self.btn.config(state="disabled")

        def work():
            try:
                self.srv.start()
                self.q.put(("log", "Server started."))
                self.root.after(0, self._started)
            except Exception as e:
                self.q.put(("log", f"ERROR: {e}"))
                self.root.after(0, lambda: (self.set_stopped(),
                                            messagebox.showerror("Could not start", str(e))))

        threading.Thread(target=work, daemon=True).start()

    def _started(self):
        self.status.set("Running")
        self.status_lbl.config(foreground="#080")
        self.btn.config(text="Stop server", state="normal")
        if config["tunnel_mode"] == "off":
            self.url.set(f"http://127.0.0.1:{self.srv.port}")
            self.render_qr()
        else:
            self.url.set("(waiting for Cloudflare tunnel…)")

    def save(self, quiet=False):
        config["llm_base_url"] = self.llm_url.get().strip() or "http://127.0.0.1:8080"
        m = self.model.get().strip()
        config["default_model"] = "" if m == AUTO_MODEL else m
        config["require_tool_approval"] = self.approve.get()
        config["enable_code_exec"] = self.exec_on.get()
        if not quiet:
            self.write_log("Settings saved (applied immediately).")
            self.fetch_models()

    def new_token(self):
        if messagebox.askyesno("New token", "Generate a new access token? Paired phones must re-scan."):
            self.token.set(config.regenerate_token())
            if self.srv.running:
                self.render_qr()

    def on_close(self):
        if self.srv.running:
            self.srv.stop()
        self.root.destroy()


if __name__ == "__main__":
    if not single_instance():
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo("LocalAI Bridge", "The LocalAI Bridge control panel is already running.\n"
                                              "Look for it in the taskbar.")
        sys.exit(0)
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
