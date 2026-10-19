"""OrcaCyber-Nano-1.0 (orcarouter, Qwen3.8-27B type cybersecurity fine-tune, MTP head built in) Mix-13G on the V100.
Tuning (_build/tune-orcacyber*.ps1, mean of a code and a chat reply, thinking off):
  MTP3 32k f16 KV, vision CPU   60.3 tok/s (code 66.6 / chat 54.0), accepted 76%, 15.3 GB, image ok
  MTP4 32k                      60.2 tok/s (code 70.2 / chat 50.3), accepted 66%
  MTP3 96k q4 KV                57.1 tok/s (code 63.0 / chat 51.2), accepted 73%, 15.6 GB, image ok
  no spec 160k q4 KV            31.7 tok/s, 15.8 GB, image ok   (192k and MTP 128k: out of memory)
  no spec 32k, vision GPU       34.7 tok/s
The DFlash2 drafter of the repo is Q8_0 (2.06 GB) and does not fit next to the model on 16 GB."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
R = "orcarouter/OrcaCyber-Nano-1.0"
GGUF = "OrcaCyber-Nano-1.0-AI-Defense-Mix-13G.gguf"
MM = "mmproj-OrcaCyber-Nano-1.0-AI-Defense-F16.gguf"


def preset(pid, name, bench, ctx, kv, mtp, ub):
    rows = [["--no-mmproj-offload", "", "vision encoder on CPU"]]
    if mtp:
        rows += [["--spec-type", "draft-mtp", "the MTP head built into the model file"],
                 ["--spec-draft-n-max", str(mtp), "tokens drafted per step"], ["--spec-draft-p-min", "0", ""]]
        if kv != "f16":
            rows += [["--spec-draft-type-k", kv, ""], ["--spec-draft-type-v", kv, ""]]
    rows += [["-ngl", "all", ""], ["-c", str(ctx), "context"]]
    if kv != "f16":
        rows += [["-ctk", kv, "4-bit KV cache"], ["-ctv", kv, ""]]
    rows += [["-np", "1", ""], ["-fa", "on", ""], ["--load-mode", "none", ""], ["-b", "2048", ""], ["-ub", str(ub), ""],
             ["--cache-ram", "2048", "prompt cache in RAM, MiB"], ["--jinja", "", ""], ["--temp", "0.7", ""],
             ["--top-k", "20", ""], ["--top-p", "0.8", ""], ["--min-p", "0", ""]]
    return {"id": pid, "name": name, "kernel": "llamacpp", "kernels": ["llamacpp"], "bench": bench, "params": rows}


m = {"id": "orcacyber-nano", "name": "OrcaCyber-Nano-1.0 27B Mix-13G (MTP built in)",
     "desc": "orcarouter's cybersecurity fine-tune of a Qwen3.8-27B type model (reverse engineering, vulnerability "
             "analysis, secure code review), Mix-13G GGUF (13.0 GB) with the MTP head in the file; vision on the CPU. "
             "Gated on Hugging Face: sign in and accept access, then download the files into the model folder.",
     "files": [[R, GGUF], [R, MM]],
     "model": GGUF, "mmproj": MM,
     "presets": [
         preset("fast-32k", "FAST: 32k context, MTP 3 (60 tok/s)",
                "60.3 tok/s (code 66.6 / chat 54.0), draft accepted 76%, 15.3 GB VRAM; image ok", 32768, "f16", 3, 512),
         preset("long-96k", "96k context, MTP 3, q4 KV (57 tok/s)",
                "57.1 tok/s (code 63.0 / chat 51.2), draft accepted 73%, 15.6 GB VRAM; image ok", 98304, "q4_0", 3, 256),
         preset("max-160k", "160k context, no MTP, q4 KV (32 tok/s)",
                "31.7 tok/s, 15.8 GB VRAM; image ok (192k does not fit)", 163840, "q4_0", 0, 256),
         {"id": "full-262k-stream", "name": "FULL 262k context, KV streaming (text only)", "kernel": "kvstream",
          "kernels": ["kvstream"], "bench": "23.8 tok/s code after a 19.6k-token prompt (KV cache in system RAM, streamed over PCIe; slower as the context fills, like Unsloth: ~6-12 tok/s at 100k-257k); text only",
          "params": [["--no-mmproj", "", "text only (vision not tested with streaming)"], ["--spec-type", "none", ""],
                     ["-ngl", "999", ""], ["-c", "262144", "full context"],
                     ["--shared-device-memory-mib", "3500", "VRAM arena the KV cache streams through"],
                     ["-ctk", "q4_0", ""], ["-ctv", "q4_0", ""], ["-np", "1", ""], ["-fa", "on", ""], ["--fit", "off", ""],
                     ["-b", "256", ""], ["-ub", "256", ""], ["--jinja", "", ""], ["--temp", "0.7", ""], ["--top-k", "20", ""],
                     ["--top-p", "0.8", ""], ["--min-p", "0", ""]]}]}
c["models"] = [x for x in c["models"] if x["id"] != m["id"]] + [m]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("added", m["id"], [x["id"] for x in m["presets"]])
