"""Fusion4/Ornith: default preset without repetition penalties (they corrupt numbers, code and tool calls);
the model-card penalties stay available as a 'creative' preset."""
import json
from pathlib import Path

p = Path(__file__).with_name("catalog-src.json")
c = json.loads(p.read_text(encoding="utf-8"))
PEN = {"--presence-penalty", "--repeat-penalty", "--repeat-last-n", "--dry-multiplier"}
for mid in ("fusion4-35b-pxq2", "ornith-35b-pxq2"):
    m = next(x for x in c["models"] if x["id"] == mid)
    base = next(x for x in m["presets"] if x["id"] in ("default", "creative"))
    full = [pp for pp in base["params"]]
    plain = [pp for pp in full if pp[0] not in PEN]
    m["presets"] = [
        dict(base, id="default", name=base["name"].split(" (")[0] + " (no penalties: best for code/tools)", params=plain),
        dict(base, id="creative", name=base["name"].split(" (")[0] + " (model-card repetition penalties)",
             bench="model-card penalties: fewer loops in long prose, but they corrupt numbers, code and tool calls", params=full)]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("ok")
