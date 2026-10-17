"""RentedNoodle OrcaRouter Qwen3.8-27B uncensored GSQ-RCO IQ3_XXS v2.1 (10.4 GB, built-in MTP head, tool-use template
baked in); presets from _build/tune-orca-gsq.ps1. Small enough for 160k context with MTP and the full 262k without."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
GG = "Qwen3.8-27B-OrcaRouter-GSQ-RCO-IQ3_XXS-v2.1.gguf"


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


m = {"id": "orca-qwen3.8-27b-gsq", "name": "Qwen3.8-27B OrcaRouter Uncensored GSQ-RCO-IQ3_XXS v2.1 (MTP)",
     "desc": "OrcaRouter's abliterated (uncensored) Qwen3.8-27B, quantized by RentedNoodle with ISTA-DASLab's GSQ-RCO method "
             "(10.4 GB, MTP head built in). Small enough for 160k context with MTP, or the full 262k without.",
     "files": [["RentedNoodle/Qwen3.8-27B-OrcaRouter-GSQ-RCO-IQ3_XXS-Uncensored", GG], ["unsloth/Qwen3.8-27B-GGUF", "mmproj-F16.gguf"]],
     "model": GG, "mmproj": "mmproj-F16.gguf",
     "presets": [
         preset("fast-32k", "FAST: 32k context, MTP 4, vision on GPU (49 tok/s)",
                "48.8 tok/s (code 58.6 / chat 39.0), draft accepted 60%, 14.2 GB VRAM; image ok", 32768, "f16", 4, 512, False),
         preset("long-160k", "160k context, MTP 4, q4 KV (49 tok/s)",
                "49.1 tok/s (code 58.3 / chat 40.0), draft accepted 63%, 15.2 GB VRAM; image ok", 163840, "q4_0", 4, 256, True),
         preset("max-262k", "262k context (full), no MTP, q4 KV (28 tok/s)",
                "28.4 tok/s, 15.5 GB VRAM; image ok", 262144, "q4_0", 0, 256, True)]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
