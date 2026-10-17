"""Configuration: loaded from server/config.json, created with safe defaults on first run."""
import json
import secrets
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SERVER_DIR / "data"
CONFIG_PATH = SERVER_DIR / "config.json"

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant running on the user's own Windows PC. "
    "You can use tools to run code, browse and read files inside the allowed folders, "
    "write files, and remember facts about the user across sessions. "
    "Use tools when they help; explain what you did. Prefer Python for computation. "
    "When you learn a durable fact or preference about the user, save it with save_memory."
)


def _launcher_dir() -> str:
    """V100-LLM folder: the one this bridge sits in (V100-LLM/phone-app/server), else D:/V100-LLM."""
    root = SERVER_DIR.parent.parent
    return str(root) if (root / "gui" / "launcher.py").exists() else r"D:\V100-LLM"


def _defaults() -> dict:
    home = str(Path.home())
    return {
        "host": "127.0.0.1",          # keep on localhost; cloudflared reaches it locally
        "port": 8765,
        "llm_base_url": "http://127.0.0.1:8899",  # the model the V100-LLM launcher loads. "/v1" is added automatically
        "openai_key": "",                         # key for <url>/openai/v1 (made / refreshed in the phone app; empty = off)
        "launcher_url": "http://127.0.0.1:7860",  # V100-LLM launcher API (load / unload models from the phone)
        "launcher_dir": _launcher_dir(),          # started automatically when the phone asks for the model list
        "default_model": "",
        "auth_token": secrets.token_urlsafe(32),
        "allowed_roots": [home, str(SERVER_DIR.parent / "workspace")],
        "workspace": str(SERVER_DIR.parent / "workspace"),
        "enable_code_exec": True,
        "require_tool_approval": True,   # phone must approve run_code / write_file
        "exec_timeout_sec": 120,
        "max_tool_rounds": 10,
        "max_tokens": 16384,             # per reply (incl. thinking); some servers default to only 1024
        "context_size": 0,               # 0 = detect from the LLM server
        "tunnel_mode": "quick",          # "quick" (random trycloudflare URL), "named", or "off"
        "tunnel_token": "",              # for named tunnels (cloudflared tunnel run --token ...)
        "public_url": "",                # for named tunnels: your fixed https hostname
        "cloudflared_path": "",
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
    }


class Config:
    def __init__(self):
        self.data = _defaults()
        if CONFIG_PATH.exists():
            self.data.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
            if self.data.get("llm_base_url") == "http://localhost:11434/v1":  # old default -> llama.cpp
                self.data["llm_base_url"] = "http://127.0.0.1:8080"
        self.save()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "uploads").mkdir(exist_ok=True)
        Path(self.data["workspace"]).mkdir(parents=True, exist_ok=True)

    def save(self):
        CONFIG_PATH.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def regenerate_token(self) -> str:
        self["auth_token"] = secrets.token_urlsafe(32)
        return self.data["auth_token"]


config = Config()


def llm_api_base() -> str:
    """OpenAI-compatible base URL; accepts both http://host:port and http://host:port/v1."""
    u = config["llm_base_url"].strip().rstrip("/")
    return u if u.endswith("/v1") else u + "/v1"
