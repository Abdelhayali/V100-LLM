"""Inserts eval/results/leaderboard.md (the table) into README.md between the LEADERBOARD markers."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
readme = root / "README.md"
s = readme.read_text(encoding="utf-8")
table = (root / "eval" / "results" / "leaderboard.md").read_text(encoding="utf-8").split("\n\n", 2)[-1].strip()
block = ("<!-- LEADERBOARD -->\n## Leaderboard\n\nScores are 0-100 per category (pass rates), and Overall is their mean. "
         "Gen tok/s is the mean over replies of 64+ tokens. Prompt tok/s is measured on short prompts; see the model "
         "table for long-context prompt speed. Rebuild this table with `EVALUATE.bat`.\n\n" + table +
         "\n\n> Fusion4 and Ornith: with the model card's repetition penalties they scored **45** and **74**, because the penalties "
         "corrupt numbers, code and tool calls (8080 became 80). Their default preset leaves the penalties off, and the penalties "
         "are still available as the `creative` preset.\n<!-- /LEADERBOARD -->")
if "<!-- LEADERBOARD -->" in s:
    a, b = s.index("<!-- LEADERBOARD -->"), s.index("<!-- /LEADERBOARD -->") + len("<!-- /LEADERBOARD -->")
    s = s[:a] + block + s[b:]
else:
    s = s.replace("## Quick start", block + "\n\n## Quick start", 1)
readme.write_text(s, encoding="utf-8")
print("README leaderboard updated")
