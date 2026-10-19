"""Makes the Unlimited-OCR remote code run on a V100 (no bf16: fp16 or fp32) and on the CPU.
The upstream code hard-codes .cuda() and torch.bfloat16; this replaces them with a device and dtype
taken from the environment (OCR_DEVICE = cuda|cpu, OCR_DTYPE = float16|float32|bfloat16). Idempotent."""
from pathlib import Path

p = Path(__file__).resolve().parent / "model" / "modeling_unlimitedocr.py"
t = p.read_text(encoding="utf-8")
MARK = "# --- V100/CPU patch ---"
if MARK in t:
    print("already patched")
    raise SystemExit(0)

head = (MARK + "\n"
        "_OCR_DEV = os.environ.get('OCR_DEVICE', 'cuda')\n"
        "_OCR_DTYPE = getattr(torch, os.environ.get('OCR_DTYPE', 'float16'))\n"
        "def _ocr_autocast():\n"
        "    if _OCR_DEV == 'cuda' and _OCR_DTYPE != torch.float32:\n"
        "        return torch.autocast('cuda', dtype=_OCR_DTYPE)\n"
        "    import contextlib\n"
        "    return contextlib.nullcontext()\n")
anchor = "import time\n"
assert anchor in t
t = t.replace(anchor, anchor + head, 1)

n_ac = t.count('torch.autocast("cuda", dtype=torch.bfloat16)')
t = t.replace('torch.autocast("cuda", dtype=torch.bfloat16)', "_ocr_autocast()")
n_bf = t.count(".to(torch.bfloat16)")
t = t.replace(".to(torch.bfloat16)", ".to(_OCR_DTYPE)")
n_cu = t.count(".cuda()")
t = t.replace(".cuda()", ".to(_OCR_DEV)")
p.write_text(t, encoding="utf-8")
print(f"patched: autocast {n_ac}, bf16 casts {n_bf}, .cuda() {n_cu}")
