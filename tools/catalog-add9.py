"""huihui-ai Qwen3.8-27B abliterated GSQ-RCO-IQ3_S with built-in MTP head; presets from _build/tune-huihui-q38.ps1
(it beat the abliterated UD-IQ3_S + Unsloth MTP draft by 4-5 tok/s)."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
GG = "Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf"


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


m = {"id": "huihui-qwen3.8-27b-gsq", "name": "Qwen3.8-27B Huihui abliterated GSQ-RCO-IQ3_S (MTP)",
     "desc": "huihui-ai abliterated (uncensored) Qwen3.8-27B in ISTA-DASLab's GSQ-RCO IQ3_S quant (12.1 GB) with the MTP "
             "head built in. Vision on the CPU.",
     "files": [["huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF", GG], ["unsloth/Qwen3.8-27B-GGUF", "mmproj-F16.gguf"]],
     "model": GG, "mmproj": "mmproj-F16.gguf",
     "presets": [
         preset("fast-32k", "FAST: 32k context, MTP 3 (53 tok/s)",
                "52.5 tok/s (code 58.0 / chat 47.0), draft accepted 75%, 14.6 GB VRAM; image ok (vision on GPU runs out of memory on long prompts)", 32768, "f16", 3, 512, True),
         preset("long-96k", "96k context, MTP 4, q4 KV (51 tok/s)",
                "51.4 tok/s (code 58.5 / chat 44.2), draft accepted 65%, 15.1 GB VRAM; image ok", 98304, "q4_0", 4, 256, True),
         preset("max-192k", "192k context, no MTP, q4 KV (29 tok/s)",
                "28.7 tok/s, 15.7 GB VRAM; image ok", 196608, "q4_0", 0, 256, True)]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
