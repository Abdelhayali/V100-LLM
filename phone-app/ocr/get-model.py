"""Downloads baidu/Unlimited-OCR (MIT) into ./model, SHA-256 checked for the weights."""
import hashlib, json, subprocess, urllib.request
from pathlib import Path
REPO = "baidu/Unlimited-OCR"
DEST = Path(__file__).resolve().parent / "model"
with urllib.request.urlopen(f"https://huggingface.co/api/models/{REPO}/tree/main?recursive=true", timeout=120) as r:
    tree = [f for f in json.loads(r.read()) if f["type"] == "file"]
skip = {"model-00001-of-000001.safetensors"}          # duplicate of model.safetensors
for f in tree:
    name = f["path"]
    if name in skip or name.startswith(("assets/", "wheel/")) or name.endswith(".pdf"):
        continue
    out = DEST / name
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl.exe", "-sSfL", "--retry", "20", "--retry-all-errors", "-C", "-", "-o", str(out),
                    f"https://huggingface.co/{REPO}/resolve/main/{name}"], check=False)
    if f.get("lfs"):
        h = hashlib.sha256()
        with open(out, "rb") as fh:
            for b in iter(lambda: fh.read(8 << 20), b""):
                h.update(b)
        print(("OK " if h.hexdigest() == f["lfs"]["oid"] else "BAD ") + name, flush=True)
    else:
        print("got " + name, flush=True)
print("DONE", flush=True)
