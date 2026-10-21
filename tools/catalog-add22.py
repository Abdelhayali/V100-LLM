"""Qwen3.6-35B-A3B (Alibaba, Apache 2.0, MoE with 3B active, text + image) on the V100: unsloth MTP build
UD-IQ3_XXS 14.1 GB (MTP head in the file), vision projector F16 on the CPU. Tuning (_build/tune-qwen36.ps1, mean of
a code and a chat reply, thinking off; eval/tune-qwen36.log), every expert on the GPU:
  no MTP 128k f16 91.0 tok/s 15.9 GB | 262k f16 / q8: does not start | 262k q4 ub128 89.1, 15.2 GB
  MTP 2 / 3 / 4 at 64k f16: 115.8 / 117.4 / 116.7 tok/s (accepted 78 / 71 / 65%), 15.3 GB
  MTP 3 128k q8 111.7, 16.0 GB | 128k f16: does not start | 262k: only with 2 expert layers in RAM (74.1), image fails"""
import json
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
R = "unsloth/Qwen3.6-35B-A3B-MTP-GGUF"
GGUF = "Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf"
MM = "mmproj-F16.gguf"
SAMPLING = [["--temp", "0.7", "Qwen's non-thinking defaults"], ["--top-p", "0.8", ""], ["--top-k", "20", ""], ["--min-p", "0", ""]]
BENCH = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
    "fast-64k-mtp3": "117.4 tok/s (code 131.9 / chat 103.0), MTP 3, draft accepted 71%, 15.3 GB VRAM; image ok",
    "long-128k-mtp3": "111.7 tok/s (code 127.6 / chat 95.8), MTP 3, q8 KV, 16.0 GB VRAM; image ok",
    "full-262k": "89.1 tok/s, no MTP, q4 KV, 15.2 GB VRAM; image ok (speed with a short prompt)"}


def preset(pid, name, ctx, kv, mtp, ub, cpu_moe=0):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU"]]
    if mtp:
        rows += [["--spec-type", "draft-mtp", "the MTP head built into the model file"],
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
    ["fast-64k-mtp3", "FAST: 64k context, MTP 3 (117 tok/s)", 65536, "f16", 3, 512],
    ["long-128k-mtp3", "128k context, MTP 3, q8 KV (112 tok/s)", 131072, "q8_0", 3, 512],
    ["full-262k", "FULL 262k context, q4 KV, no MTP (89 tok/s)", 262144, "q4_0", 0, 128],
]
m = {"id": "qwen3.6-35b-a3b-mtp", "name": "Qwen3.6-35B-A3B UD-IQ3_XXS (MTP built in, vision)",
     "desc": "Alibaba's Qwen3.6 35B mixture-of-experts (3B active), Apache 2.0, unsloth MTP build UD-IQ3_XXS (14.1 GB, "
             "MTP head in the file) so every expert fits on the V100; vision projector on the CPU.",
     "files": [[R, GGUF], [R, MM]], "model": GGUF, "mmproj": MM,
     "presets": [preset(*x) for x in PRESETS]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
