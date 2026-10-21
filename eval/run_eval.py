"""
Runs the V100-LLM evaluation against an OpenAI-compatible server (llama-server or Strata) and writes
results/<label>.json. Standard library only.

  python run_eval.py --label fusion4 [--port 8899] [--skip vision]
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # portable Python does not add the script folder
import tasks as T  # noqa: E402

HERE = Path(__file__).resolve().parent
PY = sys.executable


def chat(port, messages, max_tokens=512, tools=None, timeout=900):
    body = {"messages": messages, "max_tokens": max_tokens, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False, "reasoning_strength": "low"}}   # reasoning_strength: Muse Glimmer (no "off")
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    wall = time.time() - t0
    msg = d["choices"][0]["message"]
    tm = d.get("timings") or {}
    n = tm.get("predicted_n") or (d.get("usage") or {}).get("completion_tokens") or 0
    tps = tm.get("predicted_per_second") or (n / wall if wall > 0 else 0)
    return msg, {"gen_tokens": n, "gen_tps": tps, "prompt_tps": tm.get("prompt_per_second"), "wall": wall}


def text_of(msg):
    return (msg.get("content") or "").strip()


def words_match(reply, accepted):
    r = reply.lower()
    return any(re.search(r"(?<![\w.])" + re.escape(a.lower()) + r"(?![\w])", r) for a in accepted)


# ----------------------------------------------------------------------------- tool-call parsing (lenient)
def tool_calls(msg):
    """Return [(name, args_dict)] from proper tool_calls, or from JSON / <tool_call> blocks in the content."""
    out = []
    for c in msg.get("tool_calls") or []:
        f = c.get("function", {})
        try:
            args = json.loads(f.get("arguments") or "{}")
        except Exception:
            args = {}
        out.append((f.get("name"), args))
    if out:
        return out
    content = msg.get("content") or ""
    # Qwen3.x XML style: <function=name> <parameter=key>value</parameter> ... </function>
    for fm in re.finditer(r"<function=([\w.-]+)>(.*?)</function>", content, re.S):
        args = {k: v.strip() for k, v in re.findall(r"<parameter=([\w.-]+)>(.*?)</parameter>", fm.group(2), re.S)}
        out.append((fm.group(1), args))
    # <tool_call>{"name": ..., "arguments": {...}}</tool_call>
    for tm in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", content, re.S):
        try:
            j = json.loads(tm.group(1))
            out.append((j.get("name"), j.get("arguments") or j.get("parameters") or {}))
        except Exception:
            pass
    if out:
        return out
    for m in re.finditer(r"\{[^{}]*\"name\"\s*:\s*\"(\w+)\"[^{}]*(\"arguments\"|\"parameters\")\s*:\s*(\{[^{}]*\})[^{}]*\}", content):
        try:
            out.append((m.group(1), json.loads(m.group(3))))
        except Exception:
            pass
    return out


# ----------------------------------------------------------------------------- categories
def run_coding(port, log):
    score, speeds = 0, []
    for name, prompt, tests in T.CODING:
        msg, sp = chat(port, [{"role": "user", "content": prompt + " Reply with only the Python code in one ```python block, no tests, no explanation."}], 1024)
        speeds.append(sp)
        reply = text_of(msg)
        m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, re.S)
        code = max(m, key=len) if m else reply
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code + "\n\n" + tests + "\n")
            path = f.name
        try:
            ok = subprocess.run([PY, "-I", path], capture_output=True, timeout=15).returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        Path(path).unlink(missing_ok=True)
        score += ok
        log.append({"cat": "coding", "task": name, "ok": ok})
    return 100 * score / len(T.CODING), speeds


def run_chat(port, log):
    score, speeds = 0, []
    for q, acc in T.CHAT:
        msg, sp = chat(port, [{"role": "user", "content": q}], 700)
        speeds.append(sp)
        ok = words_match(text_of(msg), acc)
        score += ok
        log.append({"cat": "chat", "task": q[:50], "ok": ok, "reply": text_of(msg)[:200]})
    return 100 * score / len(T.CHAT), speeds


def check_if(reply, kind, arg):
    r = reply.strip()
    if kind == "max_words":
        return 0 < len(r.split()) < arg
    if kind == "json_list_len":
        m = re.search(r"\[.*\]", r, re.S)
        try:
            v = json.loads(m.group(0)) if m else None
            return isinstance(v, list) and len(v) == arg and all(isinstance(x, str) for x in v) and r.startswith(("[", "```"))
        except Exception:
            return False
    if kind == "no_char":
        return arg not in r and len(r) > 10
    if kind == "exact":
        return r.strip(" .\"'") == arg
    if kind == "bullets":
        return len([l for l in r.splitlines() if l.strip().startswith("- ")]) == arg
    if kind == "endswith":
        return r.endswith(arg)
    if kind == "lowercase_contains":
        return r == r.lower() and arg in r
    if kind == "regex":
        return re.search(arg, r) is not None
    return False


def run_ifeval(port, log):
    score, speeds = 0, []
    for p, kind, arg in T.IFEVAL:
        msg, sp = chat(port, [{"role": "user", "content": p}], 400)
        speeds.append(sp)
        ok = check_if(text_of(msg), kind, arg)
        score += ok
        log.append({"cat": "ifeval", "task": p[:50], "ok": ok, "reply": text_of(msg)[:200]})
    return 100 * score / len(T.IFEVAL), speeds


def run_search(port, log):
    pts, speeds = 0.0, []
    for q, keys, results, acc in T.SEARCH:
        msgs = [{"role": "system", "content": "You can use tools. Call web_search when you need information."},
                {"role": "user", "content": q}]
        msg, sp = chat(port, msgs, 300, tools=[T.SEARCH_TOOL])
        speeds.append(sp)
        calls = [c for c in tool_calls(msg) if c[0] == "web_search"]
        called = bool(calls) and any(k in str(calls[0][1].get("query", "")).lower() for k in keys)
        first = text_of(msg)
        final_ok, final = False, ""
        rnd = 0
        while calls and rnd < 3:            # a model may search more than once (e.g. to verify); answer each with the results
            rnd += 1
            msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
                {"id": f"call_{rnd}", "type": "function", "function": {"name": "web_search", "arguments": json.dumps(calls[0][1])}}]})
            msgs.append({"role": "tool", "tool_call_id": f"call_{rnd}", "content": results})
            msg, sp2 = chat(port, msgs, 400, tools=[T.SEARCH_TOOL])
            speeds.append(sp2)
            calls = [c for c in tool_calls(msg) if c[0] == "web_search"]
            final = text_of(msg)
        if final:
            final_ok = words_match(final, acc)
        pts += 0.5 * called + 0.5 * final_ok
        log.append({"cat": "search", "task": q[:50], "called": called, "rounds": rnd, "answer_ok": final_ok,
                    "first": first[:200], "query": str(calls[0][1]) if calls else "", "reply": final[:200]})
    return 100 * pts / len(T.SEARCH), speeds


def agent_check(kind, fs, events):
    if kind == "fix_add":
        try:
            ns = {}
            exec(fs.get("utils.py", ""), ns)
            return ns["add"](2, 3) == 5 and ns["add"](-1, 1) == 0
        except Exception:
            return False
    if kind == "port_9090":
        c = fs.get("config.ini", "")
        return re.search(r"^port\s*=\s*9090\s*$", c, re.M) is not None and "host = 127.0.0.1" in c and "debug = false" in c
    if kind == "calc_result":
        return fs.get("result.txt", "").strip() == str(1234 * 5678 - 999)
    if kind == "event":
        return any(e.get("title", "").strip().lower() == "design review" and e.get("date") == "2026-11-03" and e.get("time") == "14:30" for e in events)
    if kind == "todo_file":
        return fs.get("todo.txt", "").strip() in ("b.py", "./b.py")
    return False


def run_tool(n, a, fs, events):
    """The simulated environment behind the agent tools."""
    if n == "list_files":
        return "\n".join(sorted(fs)) or "(empty)"
    if n == "read_file":
        return fs.get(str(a.get("path", "")).lstrip("./"), "ERROR: no such file")
    if n == "write_file":
        fs[str(a.get("path", "")).lstrip("./")] = str(a.get("content", ""))
        return "ok"
    if n == "calculator":
        expr = str(a.get("expression", "")).strip()
        if not re.fullmatch(r"[\d\s+\-*/().]+", expr):
            return "ERROR: bad expression"
        return str(eval(expr, {"__builtins__": {}}))
    if n == "add_event":
        events.append(a)
        return "event added"
    return "ERROR: unknown tool"


def run_agent(port, log):
    score, speeds = 0, []
    for instr, files, kind in T.AGENT:
        fs, events, steps, last = dict(files), [], 0, ""
        msgs = [{"role": "system", "content": "You are an agent. Use the tools to complete the task, then reply DONE."},
                {"role": "user", "content": instr}]
        try:
            for step in range(10):
                msg, sp = chat(port, msgs, 600, tools=T.AGENT_TOOLS)
                speeds.append(sp)
                calls = tool_calls(msg)
                last = text_of(msg)
                if not calls:
                    break
                steps += 1
                msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
                    {"id": f"c{step}_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]})
                for i, (n, a) in enumerate(calls):
                    try:
                        res = run_tool(n, a if isinstance(a, dict) else {}, fs, events)
                    except Exception as e:      # a bad tool call is the model's problem, not a harness crash
                        res = f"ERROR: {e}"
                    msgs.append({"role": "tool", "tool_call_id": f"c{step}_{i}", "content": res})
            ok = agent_check(kind, fs, events)
        except Exception as e:
            ok, last = False, f"[error] {e}"
        score += ok
        log.append({"cat": "agent", "task": kind, "ok": ok, "steps": steps, "reply": last[:200]})
    return 100 * score / len(T.AGENT), speeds


def run_vision(port, log):
    score, speeds = 0, []
    for name, q, groups in T.VISION:
        img = HERE / "images" / f"{name}.png"
        b64 = base64.b64encode(img.read_bytes()).decode()
        msg, sp = chat(port, [{"role": "user", "content": [{"type": "text", "text": q},
                                                          {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}], 100)
        speeds.append(sp)
        reply = text_of(msg)
        ok = all(words_match(reply, g) for g in groups)
        score += ok
        log.append({"cat": "vision", "task": name, "ok": ok, "reply": reply[:200]})
    return 100 * score / len(T.VISION), speeds


CATS = {"coding": run_coding, "chat": run_chat, "ifeval": run_ifeval, "search": run_search, "agent": run_agent, "vision": run_vision}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()
    res = {"label": a.label, "scores": {}, "speed": {}, "log": []}
    all_sp = []
    for cat, fn in CATS.items():
        if cat in a.skip:
            continue
        t0 = time.time()
        try:
            s, sp = fn(a.port, res["log"])
        except Exception as e:
            s, sp = 0.0, []
            res["log"].append({"cat": cat, "error": str(e)})
        res["scores"][cat] = round(s, 1)
        all_sp += sp
        print(f"  {cat:8} {s:5.1f}   ({time.time() - t0:.0f}s)", flush=True)
    long = [x for x in all_sp if x["gen_tokens"] >= 64]
    res["speed"]["gen_tps"] = round(sum(x["gen_tps"] for x in long) / len(long), 1) if long else None
    pp = [x["prompt_tps"] for x in all_sp if x.get("prompt_tps")]
    res["speed"]["prompt_tps"] = round(sorted(pp)[len(pp) // 2], 0) if pp else None
    res["overall"] = round(sum(res["scores"].values()) / len(res["scores"]), 1)
    out = HERE / "results" / f"{a.label}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"  overall {res['overall']}  gen {res['speed']['gen_tps']} tok/s  -> {out}")


if __name__ == "__main__":
    main()
