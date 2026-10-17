"""MiniCPM-V 4.7 IQ3_XS fast presets (_build/tune-minicpm-iq3xs-fast.ps1): vision encoder on the CPU frees ~0.9 GB of
VRAM, so every expert fits on the GPU up to 224k context (91 tok/s, was 41)."""
import copy
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
m = next(x for x in c["models"] if x["id"] == "minicpm-v4.7-35b")
base = next(x for x in m["presets"] if x["id"] == "262k")
base["name"] = "262k context, vision on GPU (41 tok/s)"
base["bench"] = "vision on GPU (n-cpu-moe 6); the FAST presets are quicker"
new = []
for pid, name, ctx, n, bench in [
        ("fast-192k", "FAST: 192k context, vision on CPU (91 tok/s)", "196608", "0",
         "91.3 tok/s gen (all experts on GPU, 15.7 GB VRAM); 20k-token prompt ok; image ok"),
        ("fast-224k", "FAST: 224k context, vision on CPU (91 tok/s, tight VRAM)", "229376", "0",
         "91.1 tok/s gen (all experts on GPU, 16.0 GB VRAM); 20k-token prompt ok; image ok"),
        ("fast-128k", "FAST: 128k context, vision on CPU (91 tok/s)", "131072", "0",
         "91.3 tok/s gen (all experts on GPU, 15.2 GB VRAM); 20k-token prompt ok; image ok"),
        ("fast-262k", "FAST: 262k context, vision on CPU (60 tok/s)", "262144", "2",
         "60.4 tok/s gen (n-cpu-moe 2, 15.8 GB VRAM); 20k-token prompt ok; image ok")]:
    pre = copy.deepcopy(base)
    rows = []
    for k, v, d in pre["params"]:
        if k == "-c":
            v = ctx
        if k == "--n-cpu-moe":
            v, d = n, ("all experts on the GPU" if n == "0" else f"experts of {n} layers in RAM")
        rows.append([k, v, d])
    rows.append(["--no-mmproj-offload", "", "vision encoder on the CPU (frees ~0.9 GB VRAM; images take a few seconds longer)"])
    rows.append(["--cache-ram", "2048", "prompt cache in RAM, MiB (llama.cpp default 8192)"])
    pre.update(id=pid, name=name, bench=bench, params=rows)
    new.append(pre)
m["presets"] = new + [x for x in m["presets"] if x["id"] not in {q["id"] for q in new}]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("IQ3_XS presets:", [x["id"] for x in m["presets"]])
