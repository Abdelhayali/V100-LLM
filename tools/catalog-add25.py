"""Nanbeige4.3-33B (Nanbeige, Apache 2.0, dense 33B, Llama architecture, text only) on the V100. The published IQ3_XXS
(14.9 GB) leaves no room for the cache of this dense model, so tools/make-nanbeige.py builds a plain IQ3_XXS (~13 GB)
from the Q8_0 with an importance matrix; the launcher runs it as this model's setup. Tuning (_build/tune-nanbeige.ps1,
mean of a code and a chat reply, thinking off; eval/tune-nanbeige.log):
  8k f16 31.7 tok/s 14.1 GB | 16k f16 29.7, 15.8 GB | 16k q8 27.8 | 32k q8 27.3, 16.1 GB | 32k q4 27.0, 14.4 GB
  48k q4 ub128 28.6, 15.4 GB | 64k: does not start (also with ub64)"""
import json
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
GGUF = "Nanbeige4.3-33B-IQ3_XXS.gguf"
SAMPLING = [["--temp", "0.6", ""], ["--top-p", "0.95", ""], ["--top-k", "20", ""], ["--min-p", "0", ""]]
BENCH = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
    "fast-8k": "31.7 tok/s (code 33.7 / chat 29.8), 14.1 GB VRAM",
    "mid-16k": "29.7 tok/s (code 31.4 / chat 28.0), 15.8 GB VRAM",
    "long-48k": "28.6 tok/s (code 30.4 / chat 26.9), q4 KV, 15.4 GB VRAM (64k does not fit)"}


def preset(pid, name, ctx, kv, ub):
    rows = [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if kv != "f16":
        rows += [["-ctk", kv, "quantized KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""]] + SAMPLING
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": BENCH.get(pid, ""), "params": rows}


PRESETS = json.loads(sys.argv[2]) if len(sys.argv) > 2 else [
    ["fast-8k", "FAST: 8k context (32 tok/s)", 8192, "f16", 256],
    ["mid-16k", "16k context (30 tok/s)", 16384, "f16", 256],
    ["long-48k", "48k context, q4 KV (29 tok/s)", 49152, "q4_0", 128],
]
m = {"id": "nanbeige4.3-33b", "name": "Nanbeige4.3-33B IQ3_XXS (Nanbeige, dense)",
     "desc": "Nanbeige's dense 33B (Apache 2.0, Llama architecture, text only), the teacher model of the Nanbeige4.3 "
             "series aimed at agentic coding. Built here as IQ3_XXS (~13 GB) from the Q8_0 with an importance matrix so "
             "a usable cache fits on the V100. Download missing runs tools/make-nanbeige.py (~35 GB download, ~45 min).",
     "setup": {"cmd": ["{python}", "{model}\\..\\..\\..\\tools\\make-nanbeige.py"]},
     "files": [{"name": GGUF, "size": None, "sha256": None}],
     "model": GGUF, "mmproj": "",
     "presets": [preset(*x) for x in PRESETS]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
