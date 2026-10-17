"""ISTA-DASLab Qwen3.8-27B GSQ-RCO-IQ3_S with built-in MTP head (the original of the huihui abliterated one); presets from _build/tune-ista-q38.ps1
"""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
GG = "Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf"


def preset(pid, name, bench, ctx, kv, mtp, ub, vis_cpu):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU"]] if vis_cpu else []
    if mtp:
        rows += [["--spec-type", "draft-mtp", "built-in MTP head"], ["--spec-draft-n-max", str(mtp), "tokens drafted per step"],
                 ["--spec-draft-p-min", "0", ""]]
        if kv != "f16":
            rows += [["--spec-draft-type-k", kv, ""], ["--spec-draft-type-v", kv, ""]]
    rows += [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if kv != "f16":
        rows += [["-ctk", kv, "4-bit KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""], ["--temp", "0.7", ""],
             ["--top-k", "20", ""], ["--top-p", "0.8", ""], ["--min-p", "0", ""]]
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": bench, "params": rows}


m = {"id": "ista-qwen3.8-27b-gsq", "name": "Qwen3.8-27B ISTA-DASLab GSQ-RCO-IQ3_S (MTP)",
     "desc": "Official Qwen3.8-27B in ISTA-DASLab's GSQ-RCO IQ3_S quant (12.1 GB, learned non-uniform quantization) with the MTP "
             "head built in. Vision on the CPU.",
     "files": [["ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF", GG], ["unsloth/Qwen3.8-27B-GGUF", "mmproj-F16.gguf"]],
     "model": GG, "mmproj": "mmproj-F16.gguf",
     "presets": [
         preset("fast-32k", "FAST: 32k context, MTP 4 (53 tok/s)",
                "52.5 tok/s (code 63.2 / chat 41.8), draft accepted 66%, 14.8 GB VRAM; image ok", 32768, "f16", 4, 512, True),
         preset("long-96k", "96k context, MTP 4, q4 KV (52 tok/s)",
                "51.6 tok/s (code 62.1 / chat 41.1), draft accepted 67%, 15.1 GB VRAM; image ok", 98304, "q4_0", 4, 256, True),
         preset("max-192k", "192k context, no MTP, q4 KV (27 tok/s)",
                "27.4 tok/s, 15.7 GB VRAM; image ok", 196608, "q4_0", 0, 256, True)]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
