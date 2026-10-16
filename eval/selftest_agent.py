"""Proves every v2 agent task is solvable: apply a reference fix, then the grader must accept it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_eval_hard as E  # noqa: E402
import tasks_hard as H  # noqa: E402

fixes = [
    {"stats.py": "def mean(xs):\n    return sum(xs) / len(xs)\n\ndef median(xs):\n    s = sorted(xs); n = len(s)\n    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2\n"},
    {"text.py": "import re\n\ndef shout(s):\n    return s.upper() + '!'\n\ndef slugify(t):\n    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')\n"},
    {"report.txt": "East: 100\nNorth: 150\nSouth: 100\nWest: 0\n"},
    {"parser.py": "def parse_config(text):\n    out = {}\n    for line in text.splitlines():\n        if '=' in line:\n            k, v = line.split('=', 1)\n            out[k.strip()] = v.strip()\n    return out\n",
     "app.py": "from parser import parse_config\n\ndef load(text):\n    return parse_config(text)\n"},
    {"config.json": '{"name": "svc", "enabled": true, "retries_ms": [150, 300, 600, 1200], "timeout": 2250}'},
    {"lists.py": "def merge_sorted(a, b):\n    i = j = 0; out = []\n    while i < len(a) and j < len(b):\n        if a[i] <= b[j]: out.append(a[i]); i += 1\n        else: out.append(b[j]); j += 1\n    return out + a[i:] + b[j:]\n"},
]
for (instr, files, kind), fix in zip(H.AGENT, fixes):
    fs = dict(files, **fix)
    assert not E.agent_ok(kind, dict(files), files), "unfixed project must fail: " + instr[:40]
    assert E.agent_ok(kind, fs, files), "fixed project must pass: " + instr[:40] + " | " + E.run_tests_in(fs)[1][-300:]
print("all", len(H.AGENT), "agent tasks are solvable and unfixed projects fail")
