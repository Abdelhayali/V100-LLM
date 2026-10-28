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
# Q5_K_M (prithivMLmods, 13.6 GB, MTP layer in the file; _build/tune-groot-q5.ps1, eval/tune-groot-q5.log):
#   128k f16 101.7 tok/s 15.5 GB | MTP at 128k f16 / 262k f16 / 262k q8 ub512: does not start | 262k q8 ub256 98.3, 16.1 GB
#   262k q4 98.2, 15.0 GB | MTP 2 / 3 at 64k f16: 109.4 / 106.9 (accepted 61 / 51%) | MTP 3 128k q8 98.8 | MTP 3 262k q4 96.8
R5 = "prithivMLmods/Groot-19B-A3B-261023-MTP-GGUF"
GGUF5 = "Groot-19B-A3B-261023.Q5_K_M.gguf"
BENCH.update({"q5-fast-64k-mtp2": "109.4 tok/s (code 122.5 / chat 96.3), MTP 2, draft accepted 61%, 14.8 GB VRAM; image ok",
              "q5-chat-128k": "101.7 tok/s (code 101.6 / chat 101.8), no MTP, 15.5 GB VRAM; image ok",
              "q5-full-262k": "98.2 tok/s (code 98.0 / chat 98.4), no MTP, q4 KV, 15.0 GB VRAM; image ok"})
m5 = {"id": "groot-19b-a3b-q5", "name": "Groot-19B-A3B Q5_K_M (GrootTeam, MoE, MTP, vision)",
      "desc": "The same Groot-19B-A3B-261023 as a Q5_K_M (13.6 GB, ~5.7 bits, MTP layer in the file; prithivMLmods) with the "
              "official vision projector: a little more precise than the Q4_K_M, with MTP only up to 64k context.",
      "files": [[R5, GGUF5], [R, MM]], "model": GGUF5, "mmproj": MM,
      "presets": [preset(*x) for x in [
          ["q5-fast-64k-mtp2", "FAST: 64k context, MTP 2 (109 tok/s, 123 on code)", 65536, "f16", 2, 512],
          ["q5-chat-128k", "128k context, no MTP (102 tok/s)", 131072, "f16", 0, 512],
          ["q5-full-262k", "FULL 262k context, q4 KV, no MTP (98 tok/s)", 262144, "q4_0", 0, 512]]]}
c["models"] = [x for x in c["models"] if x["id"] not in (m["id"], m5["id"])] + [m, m5]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], m5["id"])
