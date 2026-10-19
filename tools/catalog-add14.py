"""Unsloth Qwen3.8-27B UD-IQ3_S: add a long-96k preset with the DFlash2 drafter (incoai, Q4_K_M, 1.1 GB).
Measured (_build/tune-dflash2.ps1): 54.8 tok/s at 96k q4 KV (code 69.3 / chat 40.3) vs 50.6 with MTP; image ok."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
m = next(x for x in c["models"] if x["id"] == "unsloth-qwen3.8-27b-iq3s")
DF = ["incoai/Qwen3.8-27B-DFlash2-GGUF", "Qwen3.8-27B-DFlash2-Q4_K_M.gguf"]
if DF not in m["files"]:
    m["files"].append(DF)
rows = [["--no-mmproj-offload", "", "vision encoder on CPU"],
        ["--spec-type", "draft-dflash", "DFlash2 block-diffusion drafter"],
        ["--spec-draft-model", "{model:Qwen3.8-27B-DFlash2-Q4_K_M.gguf}", ""],
        ["--spec-draft-ngl", "all", ""], ["--spec-draft-n-max", "5", "tokens drafted per step (5 is fastest here)"],
        ["--spec-draft-p-min", "0", ""], ["-ngl", "all", ""], ["-c", "98304", "context"],
        ["-ctk", "q4_0", "4-bit KV cache"], ["-ctv", "q4_0", ""], ["-np", "1", ""], ["-fa", "on", ""],
        ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", "256", ""],
        ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""], ["--temp", "0.7", ""],
        ["--top-k", "20", ""], ["--top-p", "0.8", ""], ["--min-p", "0", ""]]
pre = {"id": "long-96k-dflash", "name": "96k context, DFlash2 drafter (55 tok/s)", "kernel": "llamacpp", "kernels": ["llamacpp"],
       "bench": "54.8 tok/s (code 69.3 / chat 40.3), draft accepted 59%, 15.5 GB VRAM; image ok (MTP at 96k: 50.6)",
       "params": rows}
m["presets"] = [x for x in m["presets"] if x["id"] != pre["id"]]
i = next(i for i, x in enumerate(m["presets"]) if x["id"] == "long-96k")
m["presets"].insert(i, pre)
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("presets:", [x["id"] for x in m["presets"]])
