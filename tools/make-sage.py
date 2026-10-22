"""Builds Sage-A1.5 IQ3_XXS for the 16 GB V100 (no published GGUF is small enough to keep every expert on the GPU).

  1. downloads the official Q8_0 GGUF and vision projector (InternScience) and an importance matrix (na0x2c6), each
     checked against the SHA-256 Hugging Face lists for it (tools/get-sage-source.py)
  2. converts Q8_0 -> IQ3_XXS with the importance matrix (llama-quantize from the llamacpp-b11804 or prism kernel)
  3. puts the model and the vision projector in models/sage-a1.5/model and deletes the 37.8 GB Q8_0

Run by the launcher's Download missing (catalog "setup"), or by hand:  runtime\\python\\python.exe tools\\make-sage.py
Needs ~39 GB of free disk while it runs (~15 GB after)."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "models" / "sage-a1.5"
SRC, OUT = MD / "src", MD / "model"
TARGET = OUT / "Sage-A1.5-IQ3_XXS.gguf"


def quantizer() -> Path:
    for k in ("llamacpp-b11804", "prism"):
        exe = ROOT / "_kernels" / k / "llama-quantize.exe"
        if exe.exists():
            return exe
    sys.exit("llama-quantize.exe not found: install the llamacpp-b11804 kernel first (any Flint preset -> Download missing)")


def main():
    if TARGET.exists() and TARGET.stat().st_size > 12e9:
        print("already built:", TARGET)
        return
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "get-sage-source.py")])
    if r.returncode:
        sys.exit("download failed")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = TARGET.with_suffix(".part")
    print("converting Q8_0 -> IQ3_XXS (about 40 minutes on the CPU)...", flush=True)
    # blk.40 is the MTP layer: the importance matrix has no data for it and IQ3_XXS needs some, so it stays higher
    # precision (attention q8_0, its experts q4_K): 14.1 GB in all, like Qwen3.6-35B-A3B's MTP build
    r = subprocess.run([str(quantizer()), "--allow-requantize", "--imatrix", str(SRC / "imatrix.gguf"),
                        "--tensor-type", r"blk\.40\..*exps=q4_K", "--tensor-type", r"blk\.40\.=q8_0",
                        str(SRC / "Sage-A1.5-Q8_0.gguf"), str(tmp), "IQ3_XXS"])
    if r.returncode or not tmp.exists():
        sys.exit("conversion failed")
    tmp.replace(TARGET)
    shutil.copy2(SRC / "Sage-A1.5-mmproj.gguf", OUT / "Sage-A1.5-mmproj.gguf")
    (SRC / "Sage-A1.5-Q8_0.gguf").unlink(missing_ok=True)   # 37.8 GB, no longer needed
    print("done:", TARGET, f"{TARGET.stat().st_size / 1e9:.1f} GB")


if __name__ == "__main__":
    main()
