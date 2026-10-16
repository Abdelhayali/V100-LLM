"""Records the measured V100 results in each preset's 'bench' text (idempotent)."""
import json
from pathlib import Path

p = Path(__file__).with_name("catalog-src.json")
c = json.loads(p.read_text(encoding="utf-8"))
bench = {
    ("saluki-27b", "262k"): "36-52 tok/s gen (MTP); 252k-token prompt OK (149 tok/s prompt, 13 tok/s gen at 252k); image OK",
    ("bonsai-heretic-27b", "262k"): "47-50 tok/s gen, 13.2 GB VRAM; 252k-token prompt OK (148 tok/s prompt, 6 tok/s gen at 252k); image on GPU 2.3 s",
    ("minicpm-v4.7-35b", "262k"): "39-41 tok/s gen; 252k-token prompt OK (296 tok/s prompt, 17 tok/s gen at 252k); image on GPU 3.8 s",
    ("nemotron-bolt-74b", "262k"): "~20 tok/s gen, ~275 tok/s prompt; 250k-token prompt OK (231 tok/s prompt, 12.8 tok/s gen at 250k); image OK",
    ("strata-flash-next", "262k"): "12-18 tok/s gen (expert cache 75% hit on 16 GB + PCIe 3.0); loads in ~6 min; image OK",
}
for m in c["models"]:
    for pr in m["presets"]:
        if (m["id"], pr["id"]) in bench:
            pr["bench"] = bench[(m["id"], pr["id"])]
p.write_text(json.dumps(c, indent=1), encoding="utf-8")
print("ok")
