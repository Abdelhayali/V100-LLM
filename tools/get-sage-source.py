"""Downloads what is needed to build Sage-A1.5 IQ3_XXS for the V100 (tools/quantize-sage.py): the official Q8_0 GGUF
and vision projector (InternScience) and an importance matrix (na0x2c6), into models/sage-a1.5/src. Resumes, and
checks each file against the SHA-256 Hugging Face lists for it."""
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "models" / "sage-a1.5" / "src"
FILES = [("InternScience/Sage-A1.5-Q8_0-GGUF", "Sage-A1.5-Q8_0.gguf"),
         ("na0x2c6/Sage-A1.5-GGUF", "imatrix.gguf"),
         ("InternScience/Sage-A1.5-Q8_0-GGUF", "Sage-A1.5-mmproj.gguf")]


def meta(repo, name):
    tree = json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}/tree/main", timeout=60))
    f = next(x for x in tree if x["path"] == name)
    return f["lfs"]["size"], f["lfs"]["oid"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(1 << 24):
            h.update(b)
    return h.hexdigest()


SRC.mkdir(parents=True, exist_ok=True)
for repo, name in FILES:
    size, oid = meta(repo, name)
    dest = SRC / name
    if not (dest.exists() and dest.stat().st_size == size):
        print(f"== {name} ({size / 1e9:.2f} GB) from {repo}", flush=True)
        for _ in range(8):
            r = subprocess.run(["curl.exe", "-fL", "--retry", "10", "-C", "-", "-sS", "-o", str(dest),
                                f"https://huggingface.co/{repo}/resolve/main/{name}"])
            if r.returncode in (0, 33) and dest.stat().st_size == size:
                break
    if sha256(dest) != oid:
        dest.unlink()
        sys.exit(f"checksum mismatch for {name} (deleted)")
    print(f"ok {name}", flush=True)
print("done", SRC)
