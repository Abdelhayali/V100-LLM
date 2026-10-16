"""Adds the Strata kernel/model and the Bonsai preset to catalog-src.json (idempotent)."""
import json
from pathlib import Path

p = Path(__file__).with_name("catalog-src.json")
c = json.loads(p.read_text(encoding="utf-8"))

c["kernels"]["strata"] = {
    "name": "Strata 0.1.44.1 (experimental CUDA 12 engine, sm_70)", "type": "strata",
    "desc": "Strata engine + its Python server: Qwen3.8-Flash-Next (125B MoE) from a GPU + 64 GB RAM.",
    "exe": "engine-cuda12\\strata.exe",
    "download": [{"url": "https://github.com/Abdelhayali/V100-LLM/releases/download/kernels-v1/kernel-strata.zip"}]}

bonsai = next(m for m in c["models"] if m["id"] == "bonsai-heretic-27b")
bonsai["presets"] = [{
    "id": "262k", "name": "262k context, vision on GPU (PQ2_0)", "kernel": "prism", "kernels": ["prism"],
    "bench": "47-50 tok/s gen, 13.2 GB VRAM at 262k",
    "params": [["-ngl", "99", ""], ["-c", "262144", "full native context"], ["-ctk", "q4_0", "4-bit KV cache"], ["-ctv", "q4_0", ""],
               ["-np", "1", ""], ["-fa", "on", ""], ["--no-mmap", "", ""], ["-b", "2048", ""], ["-ub", "256", ""], ["--jinja", "", ""],
               ["--temp", "1.0", "model card"], ["--top-p", "0.95", ""], ["--top-k", "20", ""]]}]

S = "Qwen3.8-Flash-Next-GSQ-RCO-IQ2_XS"
strata = {
    "id": "strata-flash-next", "name": "Strata: Qwen3.8-Flash-Next 125B IQ2_XS",
    "desc": "125B MoE run by the Strata engine: experts in RAM (needs 64 GB RAM, ~110 GB disk). Prepared by Strata's own setup.",
    "model": f"models/IQ2_XS/{S}-00001-of-00002.gguf", "mmproj": "",
    "files": [{"name": f"models/IQ2_XS/{S}-00001-of-00002.gguf", "size": None},
              {"name": f"models/IQ2_XS/{S}-00002-of-00002.gguf", "size": None},
              {"name": "models/mmproj-Qwen3.8-Flash-Next-BF16.gguf", "size": None},
              {"name": "packs/iq2_xs/dense.bin", "size": None},
              {"name": "mtp/rt/experts.bin", "size": None}],
    "setup": {"env": {"STRATA_EXPERIMENTAL_SM60": "1"},
              "cmd": ["{python}", "setup.py", "--yes", "--no-start", "--no-browser", "--family", "qwen", "--model", "IQ2_XS",
                      "--cuda", "12", "--skip-build", "--context", "262144", "--vision", "cpu", "--data-dir", "{model}"]},
    "strata": {"tokenizer": "packs/iq2_xs/tokenizer", "model_name": "qwen3.8-flash-next-iq2_xs",
               "vision": {"exe": "strata-vision.exe", "mmproj": "models/mmproj-Qwen3.8-Flash-Next-BF16.gguf",
                          "model": f"models/IQ2_XS/{S}-00001-of-00002.gguf", "gpu": False, "max_tokens": 300, "threads": 14}},
    "presets": [{
        "id": "262k", "name": "262k context, vision on CPU", "kernel": "strata", "kernels": ["strata"], "bench": "",
        "params": [["--pack", "{model:packs/iq2_xs}", ""], ["--native", f"{{model:models/IQ2_XS/{S}-00001-of-00002.gguf}}", "experts (RAM)"],
                   ["--ple-gguf", f"{{model:models/IQ2_XS/{S}-00002-of-00002.gguf}}", "29 GB lookup table (SSD)"],
                   ["--expert-profile", "{kernel}\\data\\expert-profile.bin", ""], ["--expert-cache", "auto", ""], ["--prefill", "auto", ""],
                   ["--spec", "4", "MTP draft tokens"], ["--spec-min-p", "0.5", ""], ["--mtp", "{model:mtp/rt}", ""],
                   ["--max-context", "262144", ""], ["--kv", "int8", ""], ["--kv-resident", "32768", "KV tokens kept in VRAM; rest streamed from RAM"],
                   ["--vision", "", "image encoder (CPU)"], ["--vram-reserve-mib", "700", ""]]}]}
c["models"] = [m for m in c["models"] if m["id"] != "strata-flash-next"] + [strata]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("catalog-src updated:", [m["id"] for m in c["models"]])
