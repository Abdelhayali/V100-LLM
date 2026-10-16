"""
Evaluate models one after another through the V100-LLM launcher (START-GUI.bat must be running),
then rebuild the leaderboard (results/leaderboard.html + .png + .md).

  python eval/run_all.py                         every installed model, first preset of each
  python eval/run_all.py saluki-27b fusion4-35b-pxq2
  python eval/run_all.py saluki-27b:262k          a specific preset
  python eval/run_all.py --redo                   re-run models that already have results
"""
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GUI = "http://127.0.0.1:7860"


def api(path, body=None, timeout=60):
    req = urllib.request.Request(GUI + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def wait_ready(limit=3600):
    t0 = time.time()
    while time.time() - t0 < limit:
        s = api("/api/status")
        if s["health"] == "ready":
            return True
        if s["health"] == "stopped":
            print("    server stopped:", "\n    ".join(s["log"][-5:]))
            return False
        time.sleep(5)
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")]   # e.g. --only=longctx
    redo = "--redo" in sys.argv
    hard = "--basic" not in sys.argv          # v2 (hard) is the default suite; --basic runs the old v1
    runner, resdir = ("run_eval_hard.py", "results_hard") if hard else ("run_eval.py", "results")
    try:
        cat = api("/api/catalog")
    except Exception:
        sys.exit("Start the launcher first: double-click START-GUI.bat")
    todo = []
    models = {m["id"]: m for m in cat["catalog"]["models"] if m["presets"]}
    for spec in (args or list(models)):           # in the order given on the command line
        mid, _, pid = spec.partition(":")
        m = models.get(mid)
        if m is None:
            print(f"unknown model {mid}")
            continue
        if True:
            p = next((x for x in m["presets"] if x["id"] == pid), m["presets"][0])
            installed = all(f["have"] for f in cat["status"][m["id"]]["files"])
            if not installed:
                print(f"skip {m['id']}: model files not downloaded")
                continue
            todo.append((m, p))
    for m, p in todo:
        label = f"{m['id']}" + (f"@{p['id']}" if len(m["presets"]) > 1 else "")
        if (HERE / resdir / f"{label}.json").exists() and not redo and not only:
            print(f"have {label} (use --redo to re-run)")
            continue
        print(f"== {label}  [{p['kernel']}]  {p['name']}", flush=True)
        params = [{"flag": x[0], "value": x[1], "on": True} for x in p["params"]]
        r = api("/api/start", {"id": m["id"], "preset": p["id"], "kernel": p["kernel"], "params": params})
        if not r.get("ok"):
            print("    start failed:", r.get("error"))
            continue
        if not wait_ready():
            print("    did not become ready, skipped")
            continue
        skip = [] if m.get("mmproj") or "--vision" in [x[0] for x in p["params"]] else ["vision"]
        subprocess.run([sys.executable, str(HERE / runner), "--label", label] + (["--skip"] + skip if skip else []) + (["--only"] + only if only else []), cwd=HERE)
        meta = HERE / resdir / f"{label}.json"
        if meta.exists():
            d = json.loads(meta.read_text(encoding="utf-8-sig"))
            # size = the files this preset loads: the main model plus any draft model it names (not the vision projector)
            used = {m["model"]} | {Path(str(x[1]).replace("{model:", "").rstrip("}")).as_posix() for x in p["params"] if "{model:" in str(x[1])}
            # a split GGUF (...-00001-of-00011.gguf) loads all of its shards, so count every sibling shard
            used = {re.sub(r"-00001-of-(\d+)\.gguf$", r"-*-of-\1.gguf", u) for u in used}
            mdir = ROOT / "models" / m["id"] / "model"
            size = sum(f.stat().st_size for u in used for f in mdir.glob(u) if f.is_file())
            d.update(model=m["name"], model_id=m["id"], preset=p["name"], kernel=p["kernel"], size_gb=round(size / 1e9, 1) if size else None)
            meta.write_text(json.dumps(d, indent=1), encoding="utf-8")
    api("/api/stop", {})
    subprocess.run([sys.executable, str(HERE / "make_chart.py")] + ([] if hard else ["--basic"]), cwd=HERE)


if __name__ == "__main__":
    main()
