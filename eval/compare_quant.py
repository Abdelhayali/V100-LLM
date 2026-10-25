"""Runs some hard-suite categories on whatever model llama-server has loaded on port 8899 and prints the scores, to
compare two quantizations of the same model on identical tasks. Usage: compare_quant.py <label> [categories...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_eval_hard as E   # noqa: E402

label = sys.argv[1]
cats = sys.argv[2:] or ["coding", "reasoning", "ifeval"]
for c in cats:
    log = []
    score, _ = E.CATS[c](8899, log)
    bad = [e.get("task", "")[:40] for e in log if not e.get("ok")]
    print(f"{label:28} {c:10} {score:5.1f}   failed: {bad}", flush=True)
