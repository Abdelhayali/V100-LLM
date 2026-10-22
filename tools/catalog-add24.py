"""Sage-A1.5 (Shanghai AI Lab / InternScience, Apache 2.0, 35B MoE with 3B active, Qwen3.5-MoE architecture with an MTP
layer, text + image) on the V100. No published GGUF keeps every expert on 16 GB (the smallest is 16.1 GB), so
tools/make-sage.py builds IQ3_XXS (14.1 GB) from the official Q8_0 with an importance matrix; the launcher runs it as
this model's setup. Tuning (_build/tune-sage.ps1, mean of a code and a chat reply, thinking off; eval/tune-sage.log):
  MTP 2 / 3 / 4 at 64k f16: 113.2 / 108.4 / 108.7 tok/s (accepted 73 / 60 / 52%), 15.5 GB
  no MTP 128k f16 94.0, 16.0 GB | MTP 3 128k q8: out of memory | MTP 2 128k q4 ub256 103.7, 15.3 GB
  262k q4 ub128 (no MTP) 91.5, 15.2 GB | MTP at 262k: does not start"""
import json
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
GGUF = "Sage-A1.5-IQ3_XXS.gguf"
MM = "Sage-A1.5-mmproj.gguf"
SAMPLING = [["--temp", "0.7", "Qwen-family non-thinking defaults"], ["--top-p", "0.8", ""], ["--top-k", "20", ""], ["--min-p", "0", ""]]
BENCH = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
    "fast-64k-mtp2": "113.2 tok/s (code 115.6 / chat 110.8), MTP 2, draft accepted 73%, 15.5 GB VRAM; image ok",
    "long-128k-mtp2": "103.7 tok/s (code 108.1 / chat 99.3), MTP 2, q4 KV, 15.3 GB VRAM; image ok",
    "full-262k": "91.5 tok/s, no MTP, q4 KV, 15.2 GB VRAM; image ok (speed with a short prompt)"}


def preset(pid, name, ctx, kv, mtp, ub, cpu_moe=0):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU"]]
    if mtp:
        rows += [["--spec-type", "draft-mtp", "the MTP layer built into the model"],
                 ["--spec-draft-n-max", str(mtp), "tokens drafted per step"], ["--spec-draft-p-min", "0", ""]]
        if kv != "f16":
            rows += [["--spec-draft-type-k", kv, ""], ["--spec-draft-type-v", kv, ""]]
    rows += [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if cpu_moe:
        rows += [["--n-cpu-moe", str(cpu_moe), "layers of experts in system RAM"]]
    if kv != "f16":
        rows += [["-ctk", kv, "quantized KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""]] + SAMPLING
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": BENCH.get(pid, ""), "params": rows}


PRESETS = json.loads(sys.argv[2]) if len(sys.argv) > 2 else [
    ["fast-64k-mtp2", "FAST: 64k context, MTP 2 (113 tok/s)", 65536, "f16", 2, 512],
    ["long-128k-mtp2", "128k context, MTP 2, q4 KV (104 tok/s)", 131072, "q4_0", 2, 256],
    ["full-262k", "FULL 262k context, q4 KV, no MTP (92 tok/s)", 262144, "q4_0", 0, 128],
]
m = {"id": "sage-a1.5", "name": "Sage-A1.5 35B-A3B IQ3_XXS (InternScience, MoE, MTP, vision)",
     "desc": "Shanghai AI Lab's Sage-A1.5 agentic 35B mixture-of-experts (3B active), Apache 2.0. Built here as IQ3_XXS "
             "(14.1 GB) from the official Q8_0 with an importance matrix, MTP layer kept at q8_0 / q4_K, so every expert "
             "fits on the V100. Download missing runs tools/make-sage.py (~39 GB download, ~45 min conversion).",
     # the launcher runs this instead of downloading files: our IQ3_XXS is built locally (no published GGUF fits)
     "setup": {"cmd": ["{python}", "{model}\\..\\..\\..\\tools\\make-sage.py"]},
     "files": [{"name": GGUF, "size": None, "sha256": None}, {"name": MM, "size": None, "sha256": None}],
     "model": GGUF, "mmproj": MM,
     "presets": [preset(*x) for x in PRESETS]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
