"""unsloth Qwen3.8-27B UD-IQ3_S (12 GB) with its separate MTP draft; presets from _build/tune-unsloth-q38.ps1."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
R = "unsloth/Qwen3.8-27B-GGUF"
MTP = "MTP/mtp-Qwen3.8-27B-Q4_0.gguf"


def preset(pid, name, bench, ctx, kv, mtp, ub):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU (with MTP the GPU has no room for it)"]]
    if mtp:
        rows += [["--spec-type", "draft-mtp", "MTP draft model"], ["--spec-draft-model", "{model:" + MTP + "}", ""],
                 ["--spec-draft-ngl", "all", ""], ["--spec-draft-n-max", str(mtp), "tokens drafted per step"],
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


m = {"id": "unsloth-qwen3.8-27b-iq3s", "name": "Qwen3.8-27B Unsloth UD-IQ3_S (MTP)",
     "desc": "Official Qwen3.8-27B in Unsloth's dynamic UD-IQ3_S quant (12.0 GB) with Unsloth's MTP draft model "
             "(+75% speed). Vision on the CPU. Not uncensored.",
     "files": [[R, "Qwen3.8-27B-UD-IQ3_S.gguf"], [R, MTP], [R, "mmproj-F16.gguf"]],
     "model": "Qwen3.8-27B-UD-IQ3_S.gguf", "mmproj": "mmproj-F16.gguf",
     "presets": [
         preset("fast-32k", "FAST: 32k context, MTP 4 (53 tok/s)",
                "53.4 tok/s (code 63.7 / chat 43.2), draft accepted 65%, 15.3 GB VRAM; image ok", 32768, "f16", 4, 512),
         preset("long-96k", "96k context, MTP 4, q4 KV (51 tok/s)",
                "50.6 tok/s (code 60.1 / chat 41.1), draft accepted 62%, 15.6 GB VRAM; image ok", 98304, "q4_0", 4, 256),
         preset("max-192k", "192k context, no MTP, q4 KV (28 tok/s)",
                "27.9 tok/s, 15.5 GB VRAM; image ok (262k does not fit)", 196608, "q4_0", 0, 256)]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
