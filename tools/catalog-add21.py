"""Gemma 4 on the V100 (Google, Apache 2.0, text + image):
  - 26B-A4B (MoE, 4B active): unsloth QAT UD-Q4_K_XL 14.2 GB (quantization-aware 4-bit, close to lossless)
  - 31B (dense): unsloth Q3_K_S 13.2 GB (UD-Q3_K_XL 15.4 GB loads but leaves no room for even an 8k cache;
    the QAT 4-bit is 17.3 GB)
Vision projector F16 on the CPU. Tuning (_build/tune-gemma4.ps1, mean of a code and a chat reply, thinking off):
  26B-A4B  32k f16 104.0 tok/s 15.1 GB | vision on GPU: same speed, image out of memory | 64k q8 90.2 |
           128k q8: image out of memory | 128k q4 ub256 88.8, 15.3 GB | 262k q4: does not start |
           262k q4 + 2 expert layers in RAM 69.8, 16.0 GB | 4 layers 59.3
  31B      8k f16 20.3 tok/s 14.7 GB | 16k q8 18.5 | 32k q8 18.2 | 64k q4 17.7, 15.3 GB | 128k: does not start
           (UD-Q3_K_XL 15.4 GB: no context fits; with --fit (layers on the CPU) 13.0 tok/s at 8k)"""
import json
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
SAMPLING = [["--temp", "1.0", "Google's defaults"], ["--top-p", "0.95", ""], ["--top-k", "64", ""], ["--min-p", "0", ""]]
BENCH = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {   # "model:preset" -> measured text
    "gemma4-26b-a4b-qat:fast-32k": "104.0 tok/s (code 104.1 / chat 103.8), all experts on the GPU, 15.1 GB VRAM; image ok",
    "gemma4-26b-a4b-qat:long-128k": "88.8 tok/s, q4 KV, 15.3 GB VRAM; image ok",
    "gemma4-26b-a4b-qat:full-262k": "69.8 tok/s, q4 KV, 2 layers of experts in RAM, 16.0 GB VRAM; image ok",
    "gemma4-31b:fast-8k": "20.3 tok/s (code 20.7 / chat 19.9), 14.7 GB VRAM; image ok",
    "gemma4-31b:mid-32k": "18.2 tok/s, q8 KV, 15.2 GB VRAM; image ok",
    "gemma4-31b:long-64k": "17.7 tok/s, q4 KV, 15.3 GB VRAM; image ok (128k does not fit)"}


def preset(mid, pid, name, ctx, kv, ub, cpu_moe=0):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU"], ["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if cpu_moe:
        rows += [["--n-cpu-moe", str(cpu_moe), "layers of experts in system RAM"]]
    if kv != "f16":
        rows += [["-ctk", kv, "quantized KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""]] + SAMPLING
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": BENCH.get(f"{mid}:{pid}", ""), "params": rows}


MODELS = [
    {"id": "gemma4-26b-a4b-qat", "name": "Gemma 4 26B-A4B QAT UD-Q4_K_XL (Google, MoE, vision)",
     "desc": "Google's Gemma 4 26B mixture-of-experts (4B active), Apache 2.0, quantization-aware trained 4-bit "
             "(unsloth UD-Q4_K_XL, 14.2 GB: close to lossless); vision projector on the CPU.",
     "repo": "unsloth/gemma-4-26B-A4B-it-qat-GGUF", "gguf": "gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf", "mm": "mmproj-F16.gguf",
     "presets": [["fast-32k", "FAST: 32k context (104 tok/s)", 32768, "f16", 512], ["long-128k", "128k context, q4 KV (89 tok/s)", 131072, "q4_0", 256],
                 ["full-262k", "FULL 262k context, q4 KV, 2 expert layers in RAM (70 tok/s)", 262144, "q4_0", 256, 2]]},
    {"id": "gemma4-31b", "name": "Gemma 4 31B Q3_K_S (Google, dense, vision)",
     "desc": "Google's Gemma 4 31B dense model, Apache 2.0, unsloth Q3_K_S (13.2 GB: the 15.4 GB UD-Q3_K_XL leaves no "
             "room for the cache on 16 GB, the QAT 4-bit is 17.3 GB); vision projector on the CPU.",
     "repo": "unsloth/gemma-4-31B-it-GGUF", "gguf": "gemma-4-31B-it-Q3_K_S.gguf", "mm": "mmproj-F16.gguf",
     "presets": [["fast-8k", "FAST: 8k context (20 tok/s)", 8192, "f16", 256], ["mid-32k", "32k context, q8 KV (18 tok/s)", 32768, "q8_0", 256],
                 ["long-64k", "64k context, q4 KV (18 tok/s)", 65536, "q4_0", 256]]},
]
PRESETS = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}   # model id -> [[pid, name, ctx, kv, ub, cpu_moe], ...]
for d in MODELS:
    m = {"id": d["id"], "name": d["name"], "desc": d["desc"], "files": [[d["repo"], d["gguf"]], [d["repo"], d["mm"]]],
         "model": d["gguf"], "mmproj": d["mm"],
         "presets": [preset(d["id"], *x) for x in PRESETS.get(d["id"], d["presets"])]}
    c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
    print("added", m["id"], [x["id"] for x in m["presets"]])
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
