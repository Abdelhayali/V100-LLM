"""Muse Glimmer 30B (Meta, Apache 2.0, dense, text + image) UD-Q3_K_XL (unsloth) on the V100.
Tuning (_build/tune-muse.ps1, mean of a code and a chat reply, reasoning_strength low; eval/tune-muse.log):
  no drafter 32k f16 KV            22.8 tok/s, 12.8 GB   (64k..262k q4: 21.4..20.9, context costs almost no VRAM)
  DFlash 3 / 5 / 7 / 9 / 12 / 16   37.6 / 37.5 / 44.9 / 41.1 / 42.3 / 45.3 tok/s (7: accepted 35%, 16: 21%)
  DFlash 7 128k q4 ub256           44.0 tok/s, 14.8 GB; ub512: image crashes (out of memory)
  DFlash 7 262k q4 ub128           43.3 tok/s, 15.1 GB; image ok
"""
import json
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
R = "unsloth/Muse-Glimmer-30B-GGUF"
GGUF = "Muse-Glimmer-30B-UD-Q3_K_XL.gguf"
MM = "mmproj-Muse-Glimmer-30B-Q8_0.gguf"
DF = "dflash-kquant.gguf"
SAMPLING = [["--temp", "1.0", "Meta's defaults"], ["--top-p", "0.95", ""], ["--top-k", "64", ""], ["--min-p", "0", ""]]
BENCH = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {   # preset id -> measured text
    "fast-32k-df7": "44.9 tok/s (code 58.0 / chat 31.7), DFlash 7, draft accepted 35%, 14.9 GB VRAM; image ok",
    "long-128k-df7": "44.0 tok/s (code 57.6 / chat 30.5), DFlash 7, q4 KV, 14.8 GB VRAM; image ok",
    "full-262k-df7": "43.3 tok/s (code 56.5 / chat 30.1), DFlash 7, q4 KV, 15.1 GB VRAM; image ok (speeds with a short prompt)",
    "plain-32k": "22.8 tok/s (code 23.3 / chat 22.4), no drafter, 12.8 GB VRAM; image ok"}


def preset(pid, name, ctx, kv, dflash, ub, vision_gpu=False, n_draft=5):
    rows = [] if vision_gpu else [["--no-mmproj-offload", "", "vision encoder on CPU"]]
    if dflash:
        rows += [["--spec-type", "draft-dflash", "DFlash block-diffusion drafter"], ["--spec-draft-model", "{model:%s}" % DF, ""],
                 ["--spec-draft-ngl", "all", ""], ["--spec-draft-n-max", str(n_draft), "tokens drafted per step"],
                 ["--spec-draft-p-min", "0", ""]]
    rows += [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if kv != "f16":
        rows += [["-ctk", kv, "quantized KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""]] + SAMPLING
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": BENCH.get(pid, ""), "params": rows}


PRESETS = json.loads(sys.argv[2]) if len(sys.argv) > 2 else [
    ["fast-32k-df7", "FAST: 32k context, DFlash 7 (45 tok/s)", 32768, "q8_0", True, 512, False, 7],
    ["long-128k-df7", "128k context, DFlash 7, q4 KV (44 tok/s)", 131072, "q4_0", True, 256, False, 7],
    ["full-262k-df7", "FULL 262k context, DFlash 7, q4 KV (43 tok/s)", 262144, "q4_0", True, 128, False, 7],
    ["plain-32k", "32k context, no drafter (23 tok/s, more free VRAM)", 32768, "f16", False, 512, False, 7],
]
m = {"id": "muse-glimmer-30b", "name": "Muse Glimmer 30B UD-Q3_K_XL (Meta, dense, vision)",
     "desc": "Meta's open-weight (Apache 2.0) dense 30B agentic model with image input, Unsloth Dynamic UD-Q3_K_XL "
             "(13.4 GB); vision projector Q8_0 on the CPU, DFlash drafter for speculative decoding.",
     "files": [[R, GGUF], [R, MM], [R, DF]],
     "model": GGUF, "mmproj": MM,
     "presets": [preset(*x) for x in PRESETS]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
