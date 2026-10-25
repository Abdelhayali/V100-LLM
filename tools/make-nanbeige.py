"""Builds Nanbeige4.3-33B IQ3_XXS for the 16 GB V100. The published IQ3_XXS (AtomicChat 'AD' mix) is 14.9 GB and leaves
almost no room for the cache of this dense 33B (52 layers, 8 KV heads: ~0.2 MB per token at f16), so this script makes a
plain IQ3_XXS (~13 GB) from the Q8_0 with an importance matrix:

  1. downloads the Q8_0 GGUF (AtomicChat) and the importance matrix (DogukanUrker) into models/nanbeige4.3-33b/src,
     each checked against the SHA-256 Hugging Face lists for it (resumes if interrupted)
  2. converts Q8_0 -> IQ3_XXS (llama-quantize from the llamacpp-b11804 or prism kernel)
  3. deletes the 35 GB Q8_0

Run by the launcher's Download missing (catalog "setup"), or by hand:  runtime\\python\\python.exe tools\\make-nanbeige.py
Needs ~49 GB of free disk while it runs (~13 GB after)."""
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "models" / "nanbeige4.3-33b"
SRC, OUT = MD / "src", MD / "model"
TARGET = OUT / "Nanbeige4.3-33B-IQ3_XXS.gguf"
FILES = [("AtomicChat/Nanbeige4.3-33B-GGUF", "Nanbeige4.3-33B-Q8_0.gguf"),
         ("DogukanUrker/Nanbeige4.3-33B-GGUF", "imatrix-Nanbeige4.3-33B.gguf")]


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


def download():
    SRC.mkdir(parents=True, exist_ok=True)
    for repo, name in FILES:
        size, oid = meta(repo, name)
        dest = SRC / name
        if not (dest.exists() and dest.stat().st_size == size):
            print(f"== {name} ({size / 1e9:.2f} GB) from {repo}", flush=True)
            for _ in range(8):
                r = subprocess.run(["curl.exe", "-fL", "--retry", "10", "-C", "-", "-sS", "-o", str(dest),
                                    f"https://huggingface.co/{repo}/resolve/main/{name}"])
                if r.returncode in (0, 33) and dest.exists() and dest.stat().st_size == size:
                    break
        if sha256(dest) != oid:
            dest.unlink()
            sys.exit(f"checksum mismatch for {name} (deleted)")
        print(f"ok {name}", flush=True)


def quantizer() -> Path:
    for k in ("llamacpp-b11804", "prism"):
        exe = ROOT / "_kernels" / k / "llama-quantize.exe"
        if exe.exists():
            return exe
    sys.exit("llama-quantize.exe not found: install the llamacpp-b11804 kernel first (any Flint preset -> Download missing)")


def main():
    if TARGET.exists() and TARGET.stat().st_size > 11e9:
        print("already built:", TARGET)
        return
    download()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = TARGET.with_suffix(".part")
    print("converting Q8_0 -> IQ3_XXS (about 45 minutes on the CPU)...", flush=True)
    r = subprocess.run([str(quantizer()), "--allow-requantize", "--imatrix", str(SRC / FILES[1][1]),
                        str(SRC / FILES[0][1]), str(tmp), "IQ3_XXS"])
    if r.returncode or not tmp.exists():
        sys.exit("conversion failed")
    tmp.replace(TARGET)
    (SRC / FILES[0][1]).unlink(missing_ok=True)   # 35 GB, no longer needed
    print("done:", TARGET, f"{TARGET.stat().st_size / 1e9:.1f} GB")


if __name__ == "__main__":
    main()
