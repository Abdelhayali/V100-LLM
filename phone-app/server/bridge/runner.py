"""Runs uvicorn + the Cloudflare tunnel; used by both the GUI and the headless launcher."""
import json
import socket
import threading
import time
import traceback

import httpx
import uvicorn

from .app import app, state
from .config import config, llm_api_base
from .tunnel import Tunnel


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((config["host"], port))
            return True
        except OSError:
            return False


def is_bridge_on(port: int) -> bool:
    try:
        return httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2).json().get("name") == "LocalAI Bridge"
    except Exception:
        return False


class BridgeServer:
    def __init__(self, log=print, on_url=None):
        self.log = log
        self.on_url_cb = on_url
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None
        self.tunnel: Tunnel | None = None
        self.port = config["port"]
        self.error: str | None = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive() and bool(self.server and self.server.started)

    def pairing_payload(self) -> str:
        url = state["public_url"] or f"http://127.0.0.1:{self.port}"
        return json.dumps({"url": url, "token": config["auth_token"]})

    def _on_url(self, url):
        state["public_url"] = url
        self.log(f"Public URL: {url}")
        if self.on_url_cb:
            self.on_url_cb(url)

    def _serve(self):
        try:
            self.server.run()
        except BaseException as e:  # SystemExit from uvicorn on bind errors, etc.
            self.error = f"{type(e).__name__}: {e}"
            self.log("Server crashed:\n" + traceback.format_exc())

    def _pick_port(self) -> int:
        base = config["port"]
        if port_free(base):
            return base
        if is_bridge_on(base):
            raise RuntimeError(f"LocalAI Bridge is already running on port {base} (another window or console). "
                               "Close it first, or use that one.")
        for p in range(base + 1, base + 30):
            if port_free(p):
                self.log(f"Port {base} is used by another program - using port {p} instead.")
                return p
        raise RuntimeError(f"No free port found near {base}.")

    def start(self):
        """Start API server + tunnel. Raises RuntimeError with a readable reason on failure."""
        if self.running:
            return
        self.error = None
        self.port = self._pick_port()
        cfg = uvicorn.Config(app, host=config["host"], port=self.port, log_level="warning",
                             log_config=None, proxy_headers=False, timeout_keep_alive=30)
        self.server = uvicorn.Server(cfg)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started or not self.thread.is_alive():
                break
            time.sleep(0.1)
        if not self.server.started:
            self.server.should_exit = True
            raise RuntimeError(self.error or "API server did not start (see log).")
        self.log(f"API server listening on http://{config['host']}:{self.port}")
        self.log(f"LLM backend: {llm_api_base()}")
        self.tunnel = Tunnel(self.port, on_url=self._on_url, log=self.log)
        try:
            self.tunnel.start()
        except Exception as e:
            self.log(f"Tunnel failed: {e}")

    def stop(self):
        from .agent import oc
        oc.stop()
        if self.tunnel:
            self.tunnel.stop()
        state["public_url"] = None
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=5)
        self.thread = None
        self.log("Server stopped.")
