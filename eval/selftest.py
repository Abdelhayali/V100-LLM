"""Offline self-test of the grader (no model needed): python eval/selftest.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_eval as R  # noqa: E402

xml = "<tool_call>\n<function=web_search>\n<parameter=query>\ntour de volta 2026\n</parameter>\n</function>\n</tool_call>"
assert R.tool_calls({"content": xml}) == [("web_search", {"query": "tour de volta 2026"})]
js = '<tool_call>{"name": "calculator", "arguments": {"expression": "1+2"}}</tool_call>'
assert R.tool_calls({"content": js}) == [("calculator", {"expression": "1+2"})]
api = {"tool_calls": [{"function": {"name": "read_file", "arguments": '{"path": "a.py"}'}}]}
assert R.tool_calls(api) == [("read_file", {"path": "a.py"})]
assert R.run_tool("calculator", {"expression": "  "}, {}, []).startswith("ERROR")
assert R.run_tool("calculator", {"expression": "(1234 * 5678) - 999"}, {}, []) == str(1234 * 5678 - 999)
fs = {"utils.py": "def add(a, b):\n    return a + b\n"}
assert R.agent_check("fix_add", fs, [])
assert R.words_match("The answer is 3.5 apples", ["3.5"]) and not R.words_match("35", ["3.5"])
assert R.check_if('["apple", "pear", "fig"]', "json_list_len", 3)
assert R.check_if("- a\n- b\n- c", "bullets", 3)
print("grader self-test OK")
