"""Inserts the hard-suite leaderboard (eval/results_hard/leaderboard.md) into README.md between the LEADERBOARD markers."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
readme = root / "README.md"
s = readme.read_text(encoding="utf-8-sig")
table = (root / "eval" / "results_hard" / "leaderboard.md").read_text(encoding="utf-8-sig").split("\n\n", 2)[-1].strip()
block = ("<!-- LEADERBOARD -->\n## Leaderboard (hard suite v2)\n\n"
         "![leaderboard](eval/results_hard/leaderboard.png)\n\n"
         "72 tasks in 7 categories, every one graded by code (see [Evaluating models](#evaluating-models)). Scores are 0-100 per "
         "category, and Overall is the mean of the categories. Gen tok/s is the mean generation speed over replies of 64+ tokens; "
         "prompt tok/s is measured on short prompts. Every model runs with its recommended preset from `catalog.json`. "
         "Rebuild this table with `EVALUATE.bat`.\n\n" + table +
         "\n\nNotes:\n"
         "- Long context is a ~14k-token text with three facts hidden in different places that have to be combined. Qwen3.8-27B "
         "PXQ3 runs with an 8k context preset, so the text does not fit; Ornith runs with 16k and still answered wrong.\n"
         "- Fusion4 and Ornith run without the model card's repetition penalties. With them they scored much lower, because "
         "the penalties corrupt numbers, code and tool calls (8080 became 80). The penalties are still available as the "
         "`creative` preset.\n"
         "- **Fastest preset:** MiniCPM-V 4.7 Q3 mix runs at **93 tok/s with 128k context** on the 16 GB V100 (preset `fast-128k`): the vision encoder runs on the CPU, which frees enough VRAM to keep every expert on the GPU. A 120k-token prompt was filled without a crash (36 tok/s while generating at 120k). Its scores are the same model file, scored with the 262k preset.\n"
         "- Strata runs three quantizations of the same 125B model (IQ2_XS, Q2_0 and the Coder IQ1_M with half the experts); they share one 28.8 GB n-gram table that is read from the SSD.\n"
         "- MiniCPM-V CRACK with its DSpark draft model is slower on a 16 GB card (34 vs 38.5 tok/s): the drafter needs ~1.5 GB of VRAM, so 7 more layers of experts go to RAM, and chat drafts are accepted only ~47% of the time.\n"
         "- ExLlamaV3 (Qwen3.8-27B EXL3) runs on the V100 but at ~11 tok/s, so it is not scored.\n"
         "- The older, easier suite (v1) is still in `eval/results/`; most models scored 90-100 there, which is why v2 exists.\n"
         "<!-- /LEADERBOARD -->")
if "<!-- LEADERBOARD -->" in s:
    a, b = s.index("<!-- LEADERBOARD -->"), s.index("<!-- /LEADERBOARD -->") + len("<!-- /LEADERBOARD -->")
    s = s[:a] + block + s[b:]
else:
    s = s.replace("## Quick start", block + "\n\n## Quick start", 1)
readme.write_text(s, encoding="utf-8")
print("README leaderboard updated")
