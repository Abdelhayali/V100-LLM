"""MiniCPM-V 4.7 Q3 mix fast presets: vision encoder on the CPU frees ~0.9 GB of VRAM so (almost) all experts fit on the GPU."""
import copy
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
m = next(x for x in c["models"] if x["id"] == "minicpm-v4.7-35b-q3mix")
base = next(x for x in m["presets"] if x["id"] == "262k")
base["name"] = "262k context, vision on GPU"
base["bench"] = "vision on GPU (n-cpu-moe 8); the FAST presets are quicker"
new = []
for pid, name, ctx, n, bench in [
        ("fast-128k", "FAST: 128k context, vision on CPU (93 tok/s)", "131072", "0", "93 tok/s gen (all experts on GPU, 16.1 GB VRAM); 120k-token prompt filled without a crash (36 tok/s gen at 120k); image ok"),
        ("fast-262k", "FAST: 262k context, vision on CPU (70 tok/s)", "262144", "4", "70.5 tok/s gen (n-cpu-moe 4, 16.0 GB VRAM); image ok")]:
    pre = copy.deepcopy(base)
    rows = []
    for k, v, d in pre["params"]:
        if k == "-c":
            v = ctx
        if k == "--n-cpu-moe":
            v, d = n, ("all experts on the GPU" if n == "0" else f"experts of {n} layers in RAM")
        rows.append([k, v, d])
    rows.append(["--no-mmproj-offload", "", "vision encoder on the CPU (frees ~0.9 GB VRAM; images take a few seconds longer)"])
    if not any(r[0] == "--cache-ram" for r in rows):
        rows.append(["--cache-ram", "2048", "prompt cache in RAM, MiB (llama.cpp default 8192)"])
    pre.update(id=pid, name=name, bench=bench, params=rows)
    new.append(pre)
m["presets"] = new + [x for x in m["presets"] if x["id"] not in {q["id"] for q in new} | {"fast-64k"}]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("q3mix presets:", [x["id"] for x in m["presets"]])
