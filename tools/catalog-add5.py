"""Adds the ExLlamaV3 kernel (TabbyAPI) and Qwen3.8-27B EXL3 SC 3.0bpw (branch files with SHA-256) - idempotent."""
import json
import urllib.request
from pathlib import Path

p = Path(__file__).with_name("catalog-src.json")
c = json.loads(p.read_text(encoding="utf-8"))
REPO, REV = "turboderp/Qwen3.8-27B-exl3", "SC_3.00bpw_H4_V4"
with urllib.request.urlopen(f"https://huggingface.co/api/models/{REPO}/tree/{REV}", timeout=60) as r:
    tree = json.loads(r.read())
files = []
for f in tree:
    if f.get("type") != "file" or f["path"].startswith(("cal_trace", "qbench_", ".gitattributes")):
        continue
    files.append({"name": f["path"], "repo": REPO, "size": f.get("lfs", {}).get("size", f.get("size")),
                  "sha256": f.get("lfs", {}).get("oid"), "url": f"https://huggingface.co/{REPO}/resolve/{REV}/{f['path']}"})

c["kernels"]["exllamav3"] = {
    "name": "ExLlamaV3 1.6.0 Volta fork (PR #404) + TabbyAPI (experimental)", "type": "tabby",
    "desc": "EXL3 models via TabbyAPI. Built locally for sm_70 with PyTorch 2.14.1+cu126; two Volta graph-capture fixes applied.",
    "exe": "tabbyAPI\\main.py", "download": []}
m = {"id": "qwen3.8-27b-exl3", "name": "Qwen3.8-27B EXL3 3.0bpw (SC, ExLlamaV3)",
     "desc": "turboderp's self-calibrated 3.0 bpw EXL3 with quantized vision tower. ~11.5 tok/s on V100 (EXL3 trellis decode is compute-bound on Volta).",
     "model": "config.json", "mmproj": "", "files": files,
     "presets": [{"id": "64k", "name": "64k context, Q4 cache, vision", "kernel": "exllamav3", "kernels": ["exllamav3"],
                  "bench": "~11.5 tok/s gen, 13.8 GB VRAM at 64k (Q4 cache); text + image OK",
                  "params": [["max_seq_len", "65536", "context tokens"], ["cache_size", "65536", ""], ["cache_mode", "Q4", "FP16 / Q8 / Q6 / Q4"],
                             ["vision", "true", "quantized vision tower"], ["reasoning", "true", ""], ["chunk_size", "2048", ""]]}]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added exllamav3 kernel and", m["id"], "with", len(files), "files,", round(sum(f["size"] or 0 for f in files) / 1e9, 1), "GB")
