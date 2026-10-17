"""Adds Strata presets for the two other Flash-Next quantizations that Strata's setup can prepare: Q2_0 and the Coder IQ1_M."""
import copy
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "catalog-src.json"
c = json.loads(p.read_text(encoding="utf-8-sig"))
m = next(x for x in c["models"] if x["id"] == "strata-flash-next")
base = next(x for x in m["presets"] if x["id"] == "262k")
for pid, name, pack, q, prof, bench in [
        ("q2_0", "Q2_0 (2-bit, fastest), 262k, vision on CPU", "q2_0", "Q2_0", "expert-profile.bin",
         "Q2_0: 37.6 GB of experts in RAM + the shared 28.8 GB n-gram table on SSD"),
        ("coder-iq1m", "Coder IQ1_M (half the experts, coding), 262k, vision on CPU", "coder-iq1_m", "coder-IQ1_M", "expert-profile-coder.bin",
         "Coder IQ1_M: 29.6 GB of experts in RAM + the shared 28.8 GB n-gram table on SSD")]:
    pre = copy.deepcopy(base)
    f = q.replace("coder-", "")
    gg = f"models/{q}/Qwen3.8-Flash-Next-GSQ-RCO-{f}"
    rep = {"--pack": f"{{model:packs/{pack}}}", "--native": f"{{model:{gg}-00001-of-00002.gguf}}",
           "--ple-gguf": f"{{model:{gg}-00002-of-00002.gguf}}", "--expert-profile": f"{{kernel}}\\data\\{prof}"}
    pre["params"] = [[k, rep.get(k, v), d] for k, v, d in pre["params"]]
    pre.update(id=pid, name=name, bench=bench)
    m["presets"] = [x for x in m["presets"] if x["id"] != pid] + [pre]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("strata presets:", [x["id"] for x in m["presets"]])
