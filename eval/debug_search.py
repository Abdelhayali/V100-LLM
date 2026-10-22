"""Replays the hard suite's web-search tasks on the loaded model and records every step: what the model wrote, each
tool call with its arguments, and what the tool returned. Usage: debug_search.py <out.json> [max_steps]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_eval as R          # noqa: E402
import run_eval_hard as E     # noqa: E402
H = E.H

out, max_steps = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6
report = []
for q, groups, _hops, _calc in H.SEARCH:
    msgs = [{"role": "system", "content": "You have tools: web_search and calculator. The facts asked about are not in your training data - search for them. You may search several times."},
            {"role": "user", "content": q}]
    steps, final = [], ""
    for step in range(max_steps):
        msg, sp = R.chat(8899, msgs, 600, tools=[H.SEARCH_TOOL, H.CALC_TOOL])
        calls = R.tool_calls(msg)
        st = {"step": step, "content": (msg.get("content") or "")[:600], "reasoning": len(msg.get("reasoning_content") or ""),
              "tokens": sp.get("gen_tokens"), "calls": []}
        if not calls:
            final = R.text_of(msg)
            steps.append(st)
            break
        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
            {"id": f"s{step}_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]})
        for i, (n, a) in enumerate(calls):
            a = a if isinstance(a, dict) else {}
            res = E.web(a.get("query", "")) if n == "web_search" else E.calc(a.get("expression", "")) if n == "calculator" else "ERROR: unknown tool"
            st["calls"].append({"tool": n, "args": a, "result": res[:300]})
            msgs.append({"role": "tool", "tool_call_id": f"s{step}_{i}", "content": res})
        steps.append(st)
    ok = bool(final) and all(R.words_match(final.replace("$", ""), g) for g in groups)
    report.append({"task": q, "ok": ok, "final": final[:300], "steps": steps})
    print(("PASS " if ok else "FAIL ") + q[:70], "| steps", len(steps), "| final:", final[:80].replace("\n", " "), flush=True)
Path(out).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
print("saved", out)
