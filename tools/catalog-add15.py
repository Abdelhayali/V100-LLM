"""Unsloth Qwen3.8-27B UD-Q3_K_XL (13.2 GB K-quant) with the DFlash2 drafter or the MTP draft; presets from
_build/tune-dflash2.ps1. Same speed as UD-IQ3_S on the V100 (llama.cpp's limit is the base decode), slightly
higher-bit weights; needs a 4-bit KV cache to fit with a drafter."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
R = "unsloth/Qwen3.8-27B-GGUF"
GG = "Qwen3.8-27B-UD-Q3_K_XL.gguf"
DF = "Qwen3.8-27B-DFlash2-Q4_K_M.gguf"
MTP = "MTP/mtp-Qwen3.8-27B-Q4_0.gguf"
TAIL = [["-ngl", "all", ""], None, ["-ctk", "q4_0", "4-bit KV cache"], ["-ctv", "q4_0", ""], ["-np", "1", ""],
        ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], None,
        ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""], ["--temp", "0.7", ""],
        ["--top-k", "20", ""], ["--top-p", "0.8", ""], ["--min-p", "0", ""]]


def preset(pid, name, bench, ctx, ub, spec):
    tail = [r for r in TAIL]
    tail[1] = ["-c", str(ctx), "context"]
    tail[8] = ["-ub", str(ub), ""]
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": bench,
            "params": [["--no-mmproj-offload", "", "vision encoder on CPU"]] + spec + tail}


DFLASH = [["--spec-type", "draft-dflash", "DFlash2 block-diffusion drafter"], ["--spec-draft-model", "{model:" + DF + "}", ""],
          ["--spec-draft-ngl", "all", ""], ["--spec-draft-n-max", "5", "tokens drafted per step (5 is fastest here)"],
          ["--spec-draft-p-min", "0", ""]]
MTP4 = [["--spec-type", "draft-mtp", "MTP draft model"], ["--spec-draft-model", "{model:" + MTP + "}", ""],
        ["--spec-draft-ngl", "all", ""], ["--spec-draft-n-max", "4", "tokens drafted per step"], ["--spec-draft-p-min", "0", ""],
        ["--spec-draft-type-k", "q4_0", ""], ["--spec-draft-type-v", "q4_0", ""]]
m = {"id": "unsloth-qwen3.8-27b-q3kxl", "name": "Qwen3.8-27B Unsloth UD-Q3_K_XL (DFlash2)",
     "desc": "Official Qwen3.8-27B in Unsloth's dynamic UD-Q3_K_XL K-quant (13.2 GB), with the DFlash2 drafter (1.1 GB) "
             "or the MTP draft. Vision on the CPU.",
     "files": [[R, GG], ["incoai/Qwen3.8-27B-DFlash2-GGUF", DF], [R, MTP], [R, "mmproj-F16.gguf"]],
     "model": GG, "mmproj": "mmproj-F16.gguf",
     "presets": [
         preset("dflash-64k-REMOVED", "64k context, DFlash2 drafter (55 tok/s)",
                "54.5 tok/s (code 69.9 / chat 39.1), draft accepted 58%, 15.8 GB VRAM; image ok", 65536, 256, DFLASH),
         preset("dflash-32k", "32k context, DFlash2 drafter (55 tok/s)",
                "54.5 tok/s (code 69.7 / chat 39.2), draft accepted 58%, 15.4 GB VRAM; image ok", 32768, 512, DFLASH),
         preset("mtp-32k", "32k context, MTP 4 (52 tok/s)",
                "51.7 tok/s (code 62.9 / chat 40.4), draft accepted 62%, 15.0 GB VRAM; image ok", 32768, 512, MTP4)]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
