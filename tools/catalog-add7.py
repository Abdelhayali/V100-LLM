"""MiniCPM-V 4.7 Q3 mix fast presets: vision encoder on the CPU frees ~0.9 GB of VRAM so (almost) all experts fit on the GPU."""
import copy
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
m = next(x for x in c["models"] if x["id"] == "minicpm-v4.7-35b-q3mix")
base = next(x for x in m["presets"] if x["id"] == "262k")
base["name"] = "262k context, vision on GPU (56 tok/s)"
new = []
for pid, name, ctx, n, bench in [
        ("fast-64k", "FAST: 64k context, vision on CPU (93 tok/s)", "65536", "0", "93.4 tok/s gen (all experts on GPU, 15.6 GB VRAM); image ok"),
        ("fast-128k", "FAST: 128k context, vision on CPU (85 tok/s)", "131072", "1", "85.4 tok/s gen (n-cpu-moe 1, 15.9 GB VRAM); image ok"),
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
    pre.update(id=pid, name=name, bench=bench, params=rows)
    new.append(pre)
m["presets"] = new + [x for x in m["presets"] if x["id"] not in {q["id"] for q in new}]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("q3mix presets:", [x["id"] for x in m["presets"]])
