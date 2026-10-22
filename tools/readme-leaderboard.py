"""Inserts the hard-suite leaderboard (eval/results_hard/leaderboard.md) into README.md between the LEADERBOARD markers."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
readme = root / "README.md"
s = readme.read_text(encoding="utf-8-sig")
table = (root / "eval" / "results_hard" / "leaderboard.md").read_text(encoding="utf-8-sig").split("\n\n", 2)[-1].strip()
# footnote marks (kept here so a rebuild does not drop them)
table = table.replace("| 60 (code 66) |", "| **60** (code 66)¹ |")
table = "\n".join(l.replace("| **92.6** |", "| **92.6**² |") if "Muse Glimmer" in l else l for l in table.split("\n"))
FOOTNOTES = ("\n\n¹ OrcaCyber-Nano: speed of its tuned `fast-32k` preset (MTP 3), measured as code 66.6 / chat 54.0 tok/s "
             "(mean 60.3); its mean over all eval replies is 56.9 tok/s.\n"
             "² Muse Glimmer cannot turn thinking off: it is scored at its lowest level (`reasoning_strength: low`), where it "
             "writes about 100 tokens of reasoning before each answer; the other models answer with thinking off. Its speed is "
             "the mean over all eval replies with the DFlash drafter (`fast-32k-df7`: code 58.0 / chat 31.7 tok/s).")
block = ("<!-- LEADERBOARD -->\n## Leaderboard (hard suite v2)\n\n"
         "![leaderboard](eval/results_hard/leaderboard.png)\n\n"
         "72 tasks in 7 categories, every one graded by code (see [Evaluating models](#evaluating-models)). Scores are 0-100 per "
         "category, and Overall is the mean of the categories. Gen tok/s is the mean generation speed over replies of 64+ tokens; "
         "prompt tok/s is measured on short prompts. Every model runs with its recommended preset from `catalog.json`. "
         "Rebuild this table with `EVALUATE.bat`.\n\n" + table + FOOTNOTES +
         "\n\nNotes:\n"
         "- Long context is a ~14k-token text with three facts hidden in different places that have to be combined. Qwen3.8-27B "
         "PXQ3 runs with an 8k context preset, so the text does not fit; Ornith runs with 16k and still answered wrong.\n"
         "- Fusion4 and Ornith run without the model card's repetition penalties. With them they scored much lower, because "
         "the penalties corrupt numbers, code and tool calls (8080 became 80). The penalties are still available as the "
         "`creative` preset.\n"
         "- **Muse Glimmer 30B** (Meta, dense, Apache 2.0) is #1, with the best instruction following (92) and full marks on reasoning, agent, vision and long context; web search (75) and coding (81) are its weaker parts. Its DFlash drafter doubles the speed (23 -> 45 tok/s), and its context costs almost no VRAM: the full 262k runs on the GPU at 43 tok/s (`full-262k-df7`, measured with a short prompt).\n"
         "- **Fastest overall: Qwen3.6-35B-A3B** (Alibaba, MoE, 3B active) at **119 tok/s** over the whole suite (117 tuned, 132 on code) with its built-in MTP head and every expert on the GPU (UD-IQ3_XXS, 14.1 GB); 112 tok/s at 128k, 89 at the full 262k. 88.4 overall; instruction following (50) is its weak spot.\n"
         "- **Gemma 4** (Google, Apache 2.0): the 31B dense scores 89.6 (best coding of the new models, 94) but runs at 16-20 tok/s, because only Q3_K_S (13.2 GB) leaves room for the cache on 16 GB; the larger UD-Q3_K_XL (15.4 GB) does not fit any context. The 26B-A4B QAT (quantization-aware 4-bit) runs at **104 tok/s** at 32k (98 over the suite), 89 at 128k and 70 at the full 262k, and scores 84.5 (agent tasks 67 are its weak spot).\n"
         "- **Sage-A1.5 35B-A3B** (Shanghai AI Lab, agentic MoE): no published GGUF keeps every expert on 16 GB, so it is built here as IQ3_XXS (14.1 GB) from the official Q8_0 with an importance matrix (`tools/make-sage.py`). 113 tok/s at 64k with its MTP layer, 104 at 128k, 92 at the full 262k. 77.7 overall: web search is 25 because in 5 of 8 tasks it kept searching until the suite's limit of 6 searches and never answered (it was trained for long open-ended research).\n"
         "- **Flint 40B-A2B** (Recursive, coding MoE, text only) needs llama.cpp b11804 (its architecture is newer than the patched kernel). It always reasons first and has no thinking switch; it is scored with reasoning ended at once (`--reasoning-budget 0`, preset `fast-64k-noreason`), which gave the same coding score as with reasoning (68.8) in 68 s instead of 791 s. Vision is 0 because it has no image input (76.6 over the six text categories). 87 tok/s at 64k.\n"
         "- MiniCPM-V 4.7 Q3 mix runs at **93 tok/s with 128k context** on the 16 GB V100 (preset `fast-128k`): the vision encoder runs on the CPU, which frees enough VRAM to keep every expert on the GPU. A 120k-token prompt was filled without a crash (36 tok/s while generating at 120k).\n"
         "- MiniCPM-V 4.7 IQ3_XS reaches **91 tok/s with up to 224k context** (presets `fast-192k` / `fast-224k`) the same way: vision encoder on the CPU, every expert on the GPU. It is 1 GB smaller than the Q3 mix, so the KV cache for 192-224k still fits. At the full 262k, 2 layers of experts go to RAM (60 tok/s, `fast-262k`).\n"
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
