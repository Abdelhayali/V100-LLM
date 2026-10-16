"""Adds the tuned MiniCPM-V 4.7 preset to catalog-src.json (idempotent)."""
import json
from pathlib import Path

p = Path(__file__).with_name("catalog-src.json")
c = json.loads(p.read_text(encoding="utf-8"))
m = next(x for x in c["models"] if x["id"] == "minicpm-v4.7-35b")
m["desc"] = "OpenBMB vision MoE (Qwen3.5/3.6 backbone, ~3B active): images + video frames. 6 layers' experts in RAM."
m["presets"] = [{
    "id": "262k", "name": "262k context, vision on GPU", "kernel": "llamacpp", "kernels": ["llamacpp"],
    "bench": "39-41 tok/s gen, image 3.8 s (n-cpu-moe 6 + 4-bit KV was 28% faster than 10 + 8-bit)",
    "params": [["-ngl", "99", ""], ["--n-cpu-moe", "6", "experts of 6 layers in RAM (tuned)"], ["-t", "14", "CPU threads"],
               ["--fit", "off", ""], ["-c", "262144", "full native context"], ["-ctk", "q4_0", "4-bit KV cache"], ["-ctv", "q4_0", ""],
               ["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", "512", ""], ["--jinja", "", ""],
               ["--temp", "0.7", ""], ["--top-p", "0.8", ""], ["--top-k", "20", ""]]}]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("ok")
