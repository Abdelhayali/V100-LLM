"""Adaptive KV streaming kernel (llama.cpp fork that keeps the KV cache in system RAM and streams it through a VRAM
arena) and a full-262k preset for Unsloth Qwen3.8-27B UD-IQ3_S. Measured on one V100-SXM2-16GB (PCIe 3.0), q4_0 K/V,
3500 MiB arena, no speculation: decode 12.3 tok/s at a filled 99k context, 8.9 at 185k, 6.4 at 257k (correct recall at
every depth). Plain llama.cpp is ~10% faster up to 192k but cannot start the model at 262k."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
c["kernels"]["kvstream"] = {
    "name": "llama.cpp adaptive KV streaming (db8fd5d, sm_70)",
    "desc": "RaymondHuang210129/llama.cpp-adaptive-kv-streaming: KV cache in system RAM, streamed through a VRAM arena, "
            "so Qwen3.8-27B runs the full 262k context on a 16 GB card. Qwen3.8 dense only.",
    "exe": "llama-server.exe",
    "download": [{"url": "https://github.com/Abdelhayali/V100-LLM/releases/download/kernels-v1/kernel-kvstream.zip"}],
}
m = next(x for x in c["models"] if x["id"] == "unsloth-qwen3.8-27b-iq3s")
pre = {"id": "full-262k-stream", "name": "FULL 262k context, KV streaming (6-12 tok/s)", "kernel": "kvstream",
       "kernels": ["kvstream"],
       "bench": "decode at a filled context: 12.3 tok/s at 99k, 8.9 at 185k, 6.4 at 257k (q4_0 KV, 3500 MiB arena, "
                "PCIe 3.0); text only; use max-192k or long-96k-dflash when 192k is enough (faster)",
       "params": [["--no-mmproj", "", "text only (vision not tested with streaming)"],
                  ["--spec-type", "none", ""],
                  ["-ngl", "999", ""], ["-c", "262144", "full context"],
                  ["--shared-device-memory-mib", "3500", "VRAM arena the KV cache streams through (5000 runs out of memory)"],
                  ["-ctk", "q4_0", "q4_0 K: 2.3x faster than q8_0 at 257k (less PCIe traffic)"], ["-ctv", "q4_0", ""],
                  ["-np", "1", ""], ["-fa", "on", ""], ["--fit", "off", ""], ["-b", "256", ""], ["-ub", "256", ""],
                  ["--jinja", "", ""], ["--temp", "0.7", ""], ["--top-k", "20", ""], ["--top-p", "0.8", ""], ["--min-p", "0", ""]]}
m["presets"] = [x for x in m["presets"] if x["id"] != pre["id"]] + [pre]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("presets:", [x["id"] for x in m["presets"]])
