"""Agens Volundr 32B v1 (Blockway, Apache-2.0) on one V100-SXM2-16GB.

New architecture (KDA linear attention + BCSA sparse attention + Engram memory + mHC), so it needs Blockway's llama.cpp
branch `volundr` (kernel "volundr", built for sm_70). Blockway's GGUFs start at 26.6 GB (Q4_K_M) and their 16 GB build
runs only on Agens Engine (sm_86+, Linux/Docker), so the launcher's setup step re-quantizes the official Q8_0 into a
~3.3-bit V100 mix (imatrix from 110 x 512 tokens): FFN gate/up IQ3_XXS, down IQ3_S, KDA qkv Q5_K, other projections
Q4_K, Engram tables BF16 in system RAM. 12.9 GiB on the GPU.

Measured: 19.1-19.6 tok/s decode (code / chat / Arabic, thinking off), 12.0 tok/s with a 19.6k-token prompt, prompt
processing ~200-480 tok/s; needle recall correct at 19.6k. KV cache must be f16 on this branch (q8_0 copy unsupported),
so the context is 20k at most (16.2 GB VRAM peak). No speculative decoding for this architecture in llama.cpp."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
c["kernels"]["volundr"] = {
    "name": "llama.cpp volundr branch (1a2f8ec, sm_70)",
    "desc": "BlockWayz/llama.cpp branch volundr: Agens Volundr architecture (KDA, BCSA, Engram, mHC). "
            "Includes llama-quantize and the setup that builds the V100 quant.",
    "exe": "llama-server.exe",
    "download": [{"url": "https://github.com/Abdelhayali/V100-LLM/releases/download/kernels-v1/kernel-volundr.zip"}],
}
GGUF = "Agens-Volundr-32B-v1-V100-mix.gguf"


def preset(pid, name, bench, ctx):
    return {"id": pid, "name": name, "kernel": "volundr", "kernels": ["volundr"], "bench": bench, "params": [
        ["-ngl", "99", ""], ["-ot", "engram_embd=CPU", "Engram lookup tables (4.3 GB) stay in system RAM"],
        ["-c", str(ctx), "context (f16 KV: the volundr branch has no quantized KV)"],
        ["-np", "1", ""], ["-fa", "on", ""], ["-b", "256", ""], ["-ub", "256", "smaller compute buffer"],
        ["--ctx-checkpoints", "8", "recurrent-state checkpoints for multi-turn cache reuse (168 MiB each, RAM)"],
        ["--jinja", "", ""], ["--temp", "0.6", ""], ["--top-k", "20", ""], ["--top-p", "0.95", ""]]}


m = {"id": "agens-volundr-32b", "name": "Agens Volundr 32B v1 (V100 3.3-bit mix)",
     "desc": "Blockway's agentic coding / tool-use model (Qwen3.8 based, new KDA + sparse-attention architecture, "
             "Apache-2.0). Text only. Hard eval 74.4 (coding 88, reasoning/search/agent/long-context 100, vision n/a); set thinking to Low: instructions 33 -> 100. The setup downloads the official Q8_0 (36.3 GB, checked), re-quantizes it for "
             "16 GB (19.2 GB file, 12.9 GiB on the GPU, Engram tables in RAM) and deletes the Q8_0. Needs ~56 GB of "
             "free disk during setup.",
     "model": GGUF, "mmproj": "",
     "files": [{"name": GGUF, "size": None}],
     "setup": {"cmd": ["{python}", "volundr-setup.py", "--data-dir", "{model}"]},
     "presets": [
         preset("fast-16k", "16k context (19 tok/s)",
                "19.1-19.6 tok/s decode (code / chat / Arabic), tool calls ok, 15.4 GB VRAM", 16384),
         preset("max-20k", "20k context, max (19 tok/s, 12 at a full context)",
                "19 tok/s short prompts, 12.0 tok/s with a 19.6k-token prompt (needle recall ok), 16.2 GB VRAM peak",
                20480)]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
