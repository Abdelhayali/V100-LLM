"""Unsloth Qwen3.8-27B UD-IQ3_S preset labels with the speeds measured on the V100-tuned llama.cpp kernel
(patches/llamacpp-f336359-v100-mmvq.patch): tg 30.6 -> 33.7 t/s plain; DFlash2 96k ~58 t/s mean of code+chat."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
m = next(x for x in c["models"] if x["id"] == "unsloth-qwen3.8-27b-iq3s")
labels = {
    "fast-32k": ("FAST: 32k context, MTP 4 (55 tok/s)",
                 "54.8 tok/s mean of code+chat (code 65 / chat 44) with the V100 kernel; 15.3 GB VRAM; image ok"),
    "long-96k-dflash": ("96k context, DFlash2 drafter (58 tok/s, code ~73)",
                        "~58 tok/s mean of code+chat (code ~73 / chat ~42), draft accepted 59%, with the V100 kernel; 15.5 GB VRAM; image ok"),
    "long-96k": ("96k context, MTP 4, q4 KV (51 tok/s)", None),
    "max-192k": ("192k context, no MTP, q4 KV (31 tok/s; 14 at a filled 99k, 10 at 185k)",
                 "~31 tok/s on short prompts with the V100 kernel; decode at a filled context: 14.1 tok/s at 99k, 9.7 at 185k; image ok"),
}
for pre in m["presets"]:
    if pre["id"] in labels:
        name, bench = labels[pre["id"]]
        pre["name"] = name
        if bench:
            pre["bench"] = bench
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print([(x["id"], x["name"]) for x in m["presets"]])
