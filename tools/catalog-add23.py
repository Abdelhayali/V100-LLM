"""Flint 40B-A2B (Recursive, Apache 2.0, MoE ~2.5B active, text only, coding) on the V100, plus the engine it needs.

Flint's architecture (FlintForCausalLM) arrived in llama.cpp on 2026-10-21 (PR #30928), after the V100-patched
llamacpp kernel was built, so it runs on the official b11804 Windows CUDA 12.4 build (CUDA 12: still has the V100's
sm_70; CUDA 13 dropped it). unsloth UD-IQ3_XXS 14.5 GB keeps every expert on the GPU. Tuning (_build/tune-flint.ps1, mean of a code and a chat reply;
eval/tune-flint.log): its KV cache is large (full attention), so longer contexts need a smaller cache and buffers:
  64k f16 ub512 86.6 tok/s 16.0 GB | 64k q8 ub256 77.7 | 128k f16 / q8 ub512: out of memory | 128k q8 ub128: fails
  128k q4 ub256 77.9, 15.4 GB | 262k: only with 4 expert layers in RAM (q4, ub128) 65.3, 16.1 GB"""
import json
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
REL = "https://github.com/ggml-org/llama.cpp/releases/download/b11804/"
c["kernels"]["llamacpp-b11804"] = {
    "name": "llama.cpp b11804 official (CUDA 12.4, sm_70)",
    "desc": "Upstream llama.cpp release b11804 (2026-10-22), unpatched: Flint and other models newer than the patched kernel.",
    "exe": "llama-server.exe",
    "download": [{"url": REL + "llama-b11804-bin-win-cuda-12.4-x64.zip"}, {"url": REL + "cudart-llama-bin-win-cuda-12.4-x64.zip"}]}

R = "unsloth/flint-GGUF"
GGUF = "flint-UD-IQ3_XXS.gguf"
SAMPLING = [["--temp", "0.6", ""], ["--top-p", "0.95", ""], ["--top-k", "20", ""], ["--min-p", "0", ""]]
BENCH = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
    "fast-64k": "86.6 tok/s (code 86.3 / chat 86.9), every expert on the GPU, 16.0 GB VRAM",
    "fast-64k-noreason": "same speed; reasoning ended at once (a coding answer: ~500 tokens instead of ~2,080)",
    "long-128k": "77.9 tok/s, q4 KV, 15.4 GB VRAM",
    "full-262k": "65.3 tok/s, q4 KV, 4 layers of experts in RAM, 16.1 GB VRAM (speed with a short prompt)"}


def preset(pid, name, ctx, kv, ub, cpu_moe=0, no_reasoning=False):
    rows = [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if no_reasoning:   # Flint has no thinking switch: a budget of 0 ends its reasoning at once
        rows += [["--reasoning-budget", "0", "answer without reasoning (about 4x faster replies)"]]
    if cpu_moe:
        rows += [["--n-cpu-moe", str(cpu_moe), "layers of experts in system RAM"]]
    if kv != "f16":
        rows += [["-ctk", kv, "quantized KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""]] + SAMPLING
    return {"id": pid, "name": name, "kernel": "llamacpp-b11804", "kernels": ["llamacpp-b11804"], "bench": BENCH.get(pid, ""), "params": rows}


PRESETS = json.loads(sys.argv[2]) if len(sys.argv) > 2 else [
    ["fast-64k", "FAST: 64k context (87 tok/s)", 65536, "f16", 512],
    ["fast-64k-noreason", "64k context, no reasoning (87 tok/s, much shorter replies)", 65536, "f16", 512, 0, True],
    ["long-128k", "128k context, q4 KV (78 tok/s)", 131072, "q4_0", 256],
    ["full-262k", "FULL 262k context, q4 KV, 4 expert layers in RAM (65 tok/s)", 262144, "q4_0", 128, 4],
]
m = {"id": "flint-40b-a2b", "name": "Flint 40B-A2B UD-IQ3_XXS (Recursive, MoE, coding)",
     "desc": "Recursive's open-weight (Apache 2.0) coding model: 40B mixture-of-experts with ~2.5B active, unsloth "
             "UD-IQ3_XXS (14.5 GB) so every expert fits on the V100. Text only. Runs on the official llama.cpp b11804.",
     "files": [[R, GGUF]], "model": GGUF, "mmproj": "",
     "eval_token_scale": 4,   # always reasons first (~1,800 tokens on a coding task), no thinking switch
     "presets": [preset(*x) for x in PRESETS]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added kernel llamacpp-b11804 and", m["id"], [x["id"] for x in m["presets"]])
