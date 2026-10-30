"""Three newer Qwen3.8-27B GGUFs with the MTP head built in (dense, hybrid) on the V100 16 GB, all tuned with
_build/tune-q38-mtp.ps1 (mean of a code and a chat reply, thinking off; every config also gets the test image and a
~7k-token prompt, which catches out-of-memory crashes short prompts miss). Logs: eval/tune-<tag>.log.

byteshape IQ4_XS-3.84bpw (ShapeLearn, 13.1 GB, Apache 2.0; tag byteshape-q38):
  no drafter 64k q8 31.8 | 128k q4 29.5 | 32k f16 / 128k MTP / 262k: do not start or fit
  MTP 3 32k q8 53.2 tok/s (accepted 73%), 14.4 GB | MTP 2 51.3 | MTP 4 51.4 | MTP 3 64k q4 52.0 | 64k q8: image/long prompt crash
  MTP 3 96k q4 52.8, 15.6 GB | DFlash2 4 16k / 32k q4 55.6 / 54.6
Swift-1.5 GSQ-RCO IQ3_S-mtp (ukisai, 12.1 GB, Swift open license; tag swift15-q38):
  no drafter 64k q8 33.3 | 128k q4 31.0 | MTP 3 32k q8 54.6 (77%), 13.8 GB | MTP 2 52.4 | MTP 3 64k q4 52.4
  MTP 3 96k q4 52.7, 14.9 GB | MTP 3 128k q4: image / long prompt crash | DFlash2 4 32k q4 55.8
Coder390 Q3LynnStyle16G-MTP (nerkyor, 13.3 GB; tag coder390-q38):
  no drafter 64k q8 29.2 | 128k q4 29.1 | MTP 3 32k q8 52.6 (72%), 14.4 GB | MTP 2 51.0 | MTP 3 64k q4 54.1
  MTP 3 96k q4 54.5, 15.6 GB | MTP 3 128k q4: does not start | DFlash2 4 32k q4 55.9"""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
SAMPLING = [["--temp", "0.7", "Qwen's non-thinking defaults"], ["--top-p", "0.8", ""], ["--top-k", "20", ""], ["--min-p", "0", ""]]


def preset(pid, name, ctx, kv, mtp, ub, bench):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU"]]
    if mtp:
        rows += [["--spec-type", "draft-mtp", "the MTP head built into the model file"],
                 ["--spec-draft-n-max", str(mtp), "tokens drafted per step"], ["--spec-draft-p-min", "0", ""]]
        if kv != "f16":
            rows += [["--spec-draft-type-k", kv, ""], ["--spec-draft-type-v", kv, ""]]
    rows += [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if kv != "f16":
        rows += [["-ctk", kv, "quantized KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""]] + SAMPLING
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": bench, "params": rows}


def presets(fast, long, full):
    return [preset("fast-32k-mtp3", f"FAST: 32k context, MTP 3 ({fast[0]:.0f} tok/s)", 32768, "q8_0", 3, 512,
                   f"{fast[0]} tok/s (code {fast[1]} / chat {fast[2]}), MTP 3, q8 KV, {fast[3]} GB VRAM; image ok, 7k prompt ok"),
            preset("long-96k-mtp3", f"96k context, MTP 3, q4 KV ({long[0]:.0f} tok/s)", 98304, "q4_0", 3, 256,
                   f"{long[0]} tok/s (code {long[1]} / chat {long[2]}), MTP 3, q4 KV, {long[3]} GB VRAM; image ok, 7k prompt ok"),
            preset("max-128k", f"128k context, q4 KV, no MTP ({full[0]:.0f} tok/s)", 131072, "q4_0", 0, 256,
                   f"{full[0]} tok/s (code {full[1]} / chat {full[2]}), q4 KV, {full[3]} GB VRAM; image ok, 7k prompt ok")]


UNS = "unsloth/Qwen3.8-27B-GGUF"
NER = "nerkyor/Qwen3.8-27B-Coder390-EfficientThink-Opus5.5-GPT6Astra-Grok4.7-DSV4Pro-K3-SFT-RLOO-MTP-DFlash2"
models = [
    {"id": "byteshape-qwen3.8-27b-iq4xs", "name": "Qwen3.8-27B ByteShape IQ4_XS-3.84bpw (MTP built in)",
     "desc": "ByteShape's ShapeLearn quantization of Qwen3.8-27B (Apache 2.0): the data type of every tensor is learned, "
             "3.84 bits per weight in 13.1 GB, so a ~4-bit model with its MTP head and 96k context fits on the V100.",
     "files": [["byteshape/Qwen3.8-27B-GGUF", "Qwen3.8-27B-IQ4_XS-3.84bpw.gguf"], ["byteshape/Qwen3.8-27B-GGUF", "mmproj-bf16.gguf"]],
     "model": "Qwen3.8-27B-IQ4_XS-3.84bpw.gguf", "mmproj": "mmproj-bf16.gguf",
     "presets": presets((53.2, 60.6, 45.7, 14.4), (52.8, 59.8, 45.8, 15.6), (29.5, 30.6, 28.3, 15.1))},
    {"id": "swift15-qwen3.8-27b-gsq", "name": "Swift-1.5 Qwen3.8-27B GSQ-RCO IQ3_S (MTP built in)",
     "desc": "ukisai's Swift 1.5 (post-trained Qwen3.8-27B for agentic and coding work, ~58% fewer thinking tokens; Swift "
             "open license) with ISTA-DASLab's GSQ-RCO per-tensor allocation, IQ3_S tier with the MTP head (12.1 GB).",
     "files": [["ukisai/Swift-1.5-Qwen3.8-27B-GSQ-RCO-GGUF", "Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf"], [UNS, "mmproj-F16.gguf"]],
     "model": "Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf", "mmproj": "mmproj-F16.gguf",
     "presets": presets((54.6, 61.9, 47.2, 13.8), (52.7, 60.3, 45.0, 14.9), (31.0, 32.0, 29.9, 14.3))},
    {"id": "coder390-qwen3.8-27b", "name": "Qwen3.8-27B Coder390 EfficientThink 16G (MTP built in)",
     "desc": "nerkyor's Coder390 (Qwen3.8-27B fine-tuned on coding distillations with SFT + RLOO, short thinking), "
             "Q3 'LynnStyle 16G' mix with the MTP head (13.3 GB) made for 16 GB cards.",
     "files": [[NER, "GGUF/Qwen3.8-27B-Coder390-Q3LynnStyle16G-MTP.gguf"], [NER, "GGUF/mmproj-Qwen3.8-27B-Q8_0.gguf"]],
     "model": "GGUF/Qwen3.8-27B-Coder390-Q3LynnStyle16G-MTP.gguf", "mmproj": "GGUF/mmproj-Qwen3.8-27B-Q8_0.gguf",
     "presets": presets((52.6, 60.1, 45.2, 14.4), (54.5, 60.2, 48.9, 15.6), (29.1, 30.4, 27.8, 15.1))},
]
ids = {m["id"] for m in models}
c["models"] = [x for x in c["models"] if x["id"] not in ids] + models
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", sorted(ids))
