"""Groot-19B-A3B-261023 (GrootTeam, Apache 2.0, MoE 19B with 3B active, post-trained from Qwen3.6-35B-A3B, Qwen3.5-MoE
architecture with an MTP layer, text + image) on the V100: the official Q4_K_M (11.7 GB, MTP layer in the file), vision
projector BF16 on the CPU. Tuning (_build/tune-groot.ps1, mean of a code and a chat reply, thinking off; eval/tune-groot.log),
every expert on the GPU:
  no MTP 128k f16 104.3 tok/s 13.8 GB | 262k f16: does not start | 262k q8 100.6, 14.5 GB
  MTP 2 / 3 / 4 at 128k f16: 107.3 / 108.5 / 101.7 tok/s (accepted 58 / 51 / 41%; code faster, chat slower), 14.7 GB
  MTP 3 262k q8 97.2, 16.1 GB | ub256 95.3, 15.8 GB"""
import json
import sys
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
R = "GrootTeam/Groot-19B-A3B-261023-GGUF"
GGUF = "Groot-19B-A3B-261023-Q4_K_M.gguf"
MM = "mmproj-Groot-19B-A3B-261023-BF16.gguf"
SAMPLING = [["--temp", "0.7", "model card non-thinking settings"], ["--top-p", "0.8", ""], ["--top-k", "20", ""], ["--min-p", "0", ""]]
BENCH = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
    "fast-128k-mtp3": "108.5 tok/s (code 126.2 / chat 90.7), MTP 3, draft accepted 51%, 14.7 GB VRAM; image ok",
    "chat-128k": "104.3 tok/s (code 104.1 / chat 104.5), no MTP, 13.8 GB VRAM; image ok",
    "full-262k": "100.6 tok/s (code 100.3 / chat 100.9), no MTP, q8 KV, 14.5 GB VRAM; image ok"}


def preset(pid, name, ctx, kv, mtp, ub):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU"]]
    if mtp:
        rows += [["--spec-type", "draft-mtp", "the MTP layer built into the model file"],
                 ["--spec-draft-n-max", str(mtp), "tokens drafted per step"], ["--spec-draft-p-min", "0", ""]]
        if kv != "f16":
            rows += [["--spec-draft-type-k", kv, ""], ["--spec-draft-type-v", kv, ""]]
    rows += [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if kv != "f16":
        rows += [["-ctk", kv, "quantized KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""]] + SAMPLING
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": BENCH.get(pid, ""), "params": rows}


PRESETS = json.loads(sys.argv[2]) if len(sys.argv) > 2 else [
    ["fast-128k-mtp3", "FAST: 128k context, MTP 3 (109 tok/s, 126 on code)", 131072, "f16", 3, 512],
    ["chat-128k", "128k context, no MTP (104 tok/s, faster chat)", 131072, "f16", 0, 512],
    ["full-262k", "FULL 262k context, q8 KV, no MTP (101 tok/s)", 262144, "q8_0", 0, 512],
]
m = {"id": "groot-19b-a3b", "name": "Groot-19B-A3B Q4_K_M (GrootTeam, MoE, MTP, vision)",
     "desc": "GrootTeam's Groot-19B-A3B-261023 (Apache 2.0), a 19B mixture-of-experts (3B active) post-trained from "
             "Qwen3.6-35B-A3B for reasoning and tool use, with short answers. Official Q4_K_M (11.7 GB, MTP layer in the "
             "file): every expert and the full 262k context fit on the V100; vision projector on the CPU.",
     "files": [[R, GGUF], [R, MM]], "model": GGUF, "mmproj": MM,
     "presets": [preset(*x) for x in PRESETS]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
