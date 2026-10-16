"""Offline self-test of the v2 grader: python eval/selftest_hard.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_eval_hard as E  # noqa: E402
import tasks_hard as H  # noqa: E402

c = E.check_rule
# each IFEVAL rule: one passing and one failing example
assert c("The sea is blue! Waves are blue! I love it!", "sentences", 3) and not c("One. Two.", "sentences", 3)
assert c("A! B!", "all_sentences_end", "!") and not c("A! B.", "all_sentences_end", "!")
assert c("blue sky, Blue sea", "word_count_exact", ("blue", 2)) and not c("blueberry blue", "word_count_exact", ("blue", 2))
j = '```json\n{"Python": 1991, "C": 1972, "Java": 1995, "Go": 2009, "Rust": 2015}\n```'
assert c(j, "json_obj_len", 5) and c(j, "json_values_int", None) and not c('{"a": "1991"}', "json_values_int", None)
assert c("dry wind\ncold sky\nfall", "lines", 3) and c("dry wind", "lowercase", None) and not c("Dry", "lowercase", None)
assert c("dry wind\ncold sky", "no_char", "e") and not c("tree", "no_char", "e")
two = "First, sleep restores you.\n***\nSecond, it helps memory."
assert c(two, "paragraphs_sep", ("***", 2)) and c(two, "para_starts", ["First", "Second"]) and not c("First only", "paragraphs_sep", ("***", 2))
nl = "1. Plan your week\n2. Take short breaks\n3. Sleep well\n4. Review notes daily\nGood luck!"
assert c(nl, "numbered", 4) and c(nl, "max_words_per_item", 8) and c(nl, "endswith", "Good luck!") and not c("1. a\n3. b", "numbered", 2)
assert c("[[Bright Future of Solar Power]]", "regex_full", r"\[\[[^\[\]]+\]\]") and c("[[Bright Future of Solar Power]]", "bracket_words", 5)
assert c("[[Bright Future of Solar Power]]", "title_case", None) and not c("[[bright future]]", "title_case", None)
assert c(" ".join(["word"] * 25), "word_count", 25) and not c(" ".join(["word"] * 24), "word_count", 25)
assert c("[53, 59, 61, 67, 71, 73]", "pylist_primes", (6, 50)) and not c("[51, 53, 59, 61, 67, 71]", "pylist_primes", (6, 50))
assert c("- one two three four\n- a b c d e f\n- a b c d e f g h", "bullet_word_counts", [4, 6, 8])
assert c("YRREBWARTS\n3", "exact_lines", ["YRREBWARTS", "3"]) and not c("YRREBWARTS\n2", "exact_lines", ["YRREBWARTS", "3"])
assert c("By the river a silver boat sat quiet and still tonight, did you see?", "ordered_words", ["river", "silver", "quiet"])
assert c("By the river a silver boat sat quiet and still tonight, did you see?", "word_range", (10, 15))
fb = H.IFEVAL[-1][1][0][1]
assert fb.startswith("1,2,X,4,5,X,Y,8,X,10,11,X,13,Y,X,16,17,X,19,20") and c(fb, "exact", fb)
# every rule kind used by the suite has a checker
for _, rules in H.IFEVAL:
    for k, a in rules:
        try:
            c("x", k, a)
        except ValueError:
            raise AssertionError("no checker for " + k)

# fake web: multi-hop chains resolve, unknown queries return nothing
assert "freiburg" in E.web("Marta Kessler cyclist").lower() and "kessler" in E.web("tour de volta 2026 winner").lower()
assert "galway" in E.web("Echo Harbor band").lower() and E.web("weather tomorrow") == "No results found."
assert E.calc("482,300 - 455,000") == "27300" and E.calc("1299/41").startswith("31.68") and E.calc("__import__('os')").startswith("ERROR")

# agent sandbox: buggy project fails, fixed project passes, editing tests counts as failure
buggy = dict(H.AGENT[0][1])
assert E.run_tests_in(buggy)[0] is False
fixed = dict(buggy, **{"stats.py": "def mean(xs):\n    return sum(xs) / len(xs)\n\ndef median(xs):\n    s = sorted(xs); n = len(s)\n    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2\n"})
assert E.run_tests_in(fixed)[0] is True and E.agent_ok("tests_pass", fixed, H.AGENT[0][1])
cheat = dict(buggy, **{"test_stats.py": "print('ok')\n"})
assert not E.agent_ok("tests_pass", cheat, H.AGENT[0][1])
assert E.agent_ok("report", {"report.txt": "East: 100\nNorth: 150\nSouth: 100\nWest: 0\n"}, {})
assert E.agent_ok("config", {"config.json": '{"name": "svc", "enabled": true, "retries_ms": [150, 300, 600, 1200], "timeout": 2250}'}, {})
# last-line extraction for reasoning answers
assert E.last_line("Work: 3*4=12\nso...\n**401**") == "401"
print("v2 grader self-test OK")
