"""Copy changed LocalAI Bridge V100 files (D:\\LocalAI-Bridge-V100) into this repo (phone-app/ and desktop-app/).

Only files that already exist here and differ are updated (new files are listed, not copied), and private or generated
paths are never touched: config.json, data/, .venv, Google tokens, chat databases, build outputs.
  python tools/sync-bridge.py          dry run
  python tools/sync-bridge.py --apply  copy
"""
import filecmp
import shutil
import sys
from pathlib import Path

SRC = Path(r"D:\LocalAI-Bridge-V100")
REPO = Path(__file__).resolve().parent.parent
PAIRS = [(SRC, REPO / "phone-app"), (SRC / "desktop", REPO / "desktop-app")]
SKIP_DIRS = {".venv", "venv", "build", ".gradle", "__pycache__", "node_modules", "workspace", "uploads", ".idea",
             "dist", "desktop"}
SKIP_FILES = {"config.json", "google_client.json", "google_token.json", "local.properties", "bridge.db", "bridge.db-wal",
              "bridge.db-shm", "tunnel_url.txt", "pairing-qr.png"}


def walk(src, dst):
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if not p.is_file() or set(rel.parts[:-1]) & SKIP_DIRS or p.name in SKIP_FILES or p.suffix in (".log", ".db"):
            continue
        if rel.parts[:2] == ("server", "data"):   # the bridge's private data (chats, memories, tokens); not android/.../data
            continue
        # the desktop pair keeps its own release/ (dist/ is skipped); allow desktop/release exe explicitly
        yield rel, p, dst / rel


def main():
    apply = "--apply" in sys.argv
    changed, new = [], []
    for src, dst in PAIRS:
        for rel, a, b in walk(src, dst):
            if b.exists():
                if not filecmp.cmp(a, b, shallow=False):
                    changed.append((a, b))
            else:
                new.append(b)
    for a, b in changed:
        print(("copied  " if apply else "changed ") + str(b.relative_to(REPO)))
        if apply:
            shutil.copy2(a, b)
    if new:
        print(f"({len(new)} files exist only in the source and were not copied, e.g. {[str(x.relative_to(REPO)) for x in new[:4]]})")


if __name__ == "__main__":
    main()
