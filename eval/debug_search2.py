"""Experiments on why a model never finishes the web-search tasks: more steps, thinking on, an explicit stop hint.
Usage: debug_search2.py  (runs on the model loaded on port 8899; only the tasks that failed for Sage)"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_eval as R          # noqa: E402
import run_eval_hard as E     # noqa: E402
H = E.H
BASE = "You have tools: web_search and calculator. The facts asked about are not in your training data - search for them. You may search several times."
HINT = " As soon as the search results contain everything the question asks for, stop searching and reply with the answer."


def chat(msgs, think, max_tokens, temp=0, tools=True):
    body = {"messages": msgs, "max_tokens": max_tokens, "temperature": temp, "top_p": 0.95,
            **({"tools": [H.SEARCH_TOOL, H.CALC_TOOL]} if tools else {}),
            "chat_template_kwargs": {"enable_thinking": think}}
    req = urllib.request.Request("http://127.0.0.1:8899/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))["choices"][0]["message"]


def run(q, groups, steps, think, system, max_tokens, temp=0, guard=False):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": q}]
    searches, seen, repeat = 0, set(), False
    for step in range(steps):
        msg = chat(msgs, think, max_tokens, temp, tools=not repeat)   # loop guard: a repeated result -> answer now
        calls = R.tool_calls(msg)
        if not calls:
            final = R.text_of(msg)
            return bool(final) and all(R.words_match(final.replace("$", ""), g) for g in groups), step + 1, searches, final
        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
            {"id": f"s{step}_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]})
        for i, (n, a) in enumerate(calls):
            a = a if isinstance(a, dict) else {}
            searches += n == "web_search"
            res = E.web(a.get("query", "")) if n == "web_search" else E.calc(a.get("expression", "")) if n == "calculator" else "ERROR: unknown tool"
            if guard and n == "web_search" and res in seen:
                repeat = True
            seen.add(res)
            msgs.append({"role": "tool", "tool_call_id": f"s{step}_{i}", "content": res})
    return False, steps, searches, ""


FAILED = list(H.SEARCH)   # all 8 tasks
EXPERIMENTS = [("suite settings (temp 0, thinking off) + loop guard", 6, False, BASE, 600, 0, True)]
for name, steps, think, system, mt, temp, guard in EXPERIMENTS:
    t0, ok_n = time.time(), 0
    print(f"== {name}", flush=True)
    for q, groups, _h, _c in FAILED:
        ok, used, searches, final = run(q, groups, steps, think, system, mt, temp, guard)
        ok_n += ok
        print(f"   {'PASS' if ok else 'FAIL'} steps {used:2} searches {searches:2} | {q[:55]} | {final[:60]!r}", flush=True)
    print(f"   -> {ok_n}/{len(FAILED)} in {time.time() - t0:.0f}s", flush=True)
