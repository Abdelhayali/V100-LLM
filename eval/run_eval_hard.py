"""
V100-LLM evaluation v2 ("hard"). Same server interface as run_eval.py; writes results/<label>.json with suite "hard".

  python run_eval_hard.py --label saluki-27b [--port 8899] [--skip vision longctx]
"""
import argparse
import ast
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_eval as R  # noqa: E402  (chat, tool_calls, text_of, words_match)
import tasks_hard as H  # noqa: E402

PY = sys.executable
FINAL = " Think step by step if needed, then give the final answer alone on the last line."


def last_line(text):
    lines = [l.strip(" *`#>") for l in text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def strip_fence(t):
    m = re.search(r"```(?:\w+)?\s*\n(.*?)```", t, re.S)
    return (m.group(1) if m else t).strip()


# ----------------------------------------------------------------------------- coding
def run_coding(port, log):
    ok_n, speeds = 0, []
    for name, prompt, tests in H.CODING:
        msg, sp = R.chat(port, [{"role": "user", "content": prompt + " Reply with only the Python code in one ```python block (no tests, no explanation)."}], 2048)
        speeds.append(sp)
        reply = R.text_of(msg)
        blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, re.S)
        code = "\n\n".join(blocks) if blocks else reply
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code + "\n\n" + tests + "\n")
            path = f.name
        try:
            r = subprocess.run([PY, "-I", path], capture_output=True, text=True, timeout=30)
            ok, err = r.returncode == 0, (r.stderr.strip().splitlines() or [""])[-1][:160]
        except subprocess.TimeoutExpired:
            ok, err = False, "timeout"
        Path(path).unlink(missing_ok=True)
        ok_n += ok
        log.append({"cat": "coding", "task": name, "ok": ok, "err": "" if ok else err})
    return 100 * ok_n / len(H.CODING), speeds


# ----------------------------------------------------------------------------- reasoning
def run_reasoning(port, log):
    ok_n, speeds = 0, []
    for q, acc in H.REASONING:
        msg, sp = R.chat(port, [{"role": "user", "content": q + FINAL}], 1500)
        speeds.append(sp)
        fin = last_line(R.text_of(msg)).lower().replace("$", "").rstrip(".")
        ok = R.words_match(fin, acc)
        ok_n += ok
        log.append({"cat": "reasoning", "task": q[:60], "ok": ok, "final": fin[:80]})
    return 100 * ok_n / len(H.REASONING), speeds


# ----------------------------------------------------------------------------- instruction following
def _words(t):
    return [w for w in re.findall(r"[A-Za-z0-9']+", t)]


def _sentences(t):
    return [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s.strip()]


def _is_prime(n):
    return n > 1 and all(n % d for d in range(2, int(n ** 0.5) + 1))


SMALL = {"a", "an", "the", "and", "or", "of", "in", "on", "for", "to", "with", "at", "by", "from", "is", "vs"}


def check_rule(t, kind, arg):
    t = t.strip()
    if kind == "sentences":
        return len(_sentences(t)) == arg
    if kind == "all_sentences_end":
        ss = _sentences(t)
        return bool(ss) and all(s.rstrip().endswith(arg) for s in ss)
    if kind == "word_count_exact":
        w, n = arg
        return len(re.findall(r"\b" + re.escape(w) + r"\b", t, re.I)) == n
    if kind in ("json_obj_len", "json_values_int"):
        try:
            d = json.loads(strip_fence(t))
        except Exception:
            return False
        if not isinstance(d, dict):
            return False
        return len(d) == arg if kind == "json_obj_len" else all(isinstance(v, int) and not isinstance(v, bool) for v in d.values())
    if kind == "lines":
        return len([l for l in t.splitlines() if l.strip()]) == arg
    if kind == "lowercase":
        return t == t.lower()
    if kind == "no_char":
        return arg.lower() not in t.lower()
    if kind == "paragraphs_sep":
        sep, n = arg
        parts = [p.strip() for p in re.split(r"(?m)^\s*" + re.escape(sep) + r"\s*$", t)]
        return len([p for p in parts if p]) == n and len(parts) == n
    if kind == "para_starts":
        parts = [p.strip() for p in re.split(r"(?m)^\s*\*\*\*\s*$", t) if p.strip()]
        return len(parts) == len(arg) and all(p.lstrip("*_ ").startswith(w) for p, w in zip(parts, arg))
    if kind == "numbered":
        items = re.findall(r"(?m)^\s*(\d+)\.\s+(.+)$", t)
        return [int(n) for n, _ in items] == list(range(1, arg + 1))
    if kind == "max_words_per_item":
        items = re.findall(r"(?m)^\s*\d+\.\s+(.+)$", t)
        return bool(items) and all(len(_words(i)) <= arg for i in items)
    if kind == "endswith":
        return t.endswith(arg)
    if kind == "regex_full":
        return re.fullmatch(arg, t) is not None
    if kind == "bracket_words":
        m = re.search(r"\[\[([^\[\]]+)\]\]", t)
        return bool(m) and len(m.group(1).split()) == arg
    if kind == "title_case":
        m = re.search(r"\[\[([^\[\]]+)\]\]", t)
        ws = (m.group(1) if m else t).split()
        return bool(ws) and all(w[0].isupper() or (i and w.lower() in SMALL) for i, w in enumerate(ws) if w[0].isalpha())
    if kind == "word_count":
        return len(_words(t)) == arg
    if kind == "pylist_primes":
        n, lo = arg
        try:
            v = ast.literal_eval(strip_fence(t))
        except Exception:
            return False
        return (isinstance(v, list) and len(v) == n and len(set(v)) == n and v == sorted(v)
                and all(isinstance(x, int) and x > lo and _is_prime(x) for x in v))
    if kind == "bullet_word_counts":
        bl = [l.strip()[2:] for l in t.splitlines() if l.strip().startswith("- ")]
        return [len(_words(b)) for b in bl] == arg
    if kind == "exact_lines":
        return [l.strip() for l in t.splitlines() if l.strip()] == arg
    if kind == "ordered_words":
        low = t.lower()
        idx = [low.find(w) for w in arg]
        return all(i >= 0 for i in idx) and idx == sorted(idx)
    if kind == "word_range":
        return arg[0] <= len(_words(t)) <= arg[1]
    if kind == "exact":
        return strip_fence(t) == arg
    raise ValueError(kind)


def run_ifeval(port, log):
    ok_n, speeds = 0, []
    for p, rules in H.IFEVAL:
        msg, sp = R.chat(port, [{"role": "user", "content": p}], 600)
        speeds.append(sp)
        t = R.text_of(msg)
        res = {k: check_rule(t, k, a) for k, a in rules}
        ok = all(res.values())
        ok_n += ok
        log.append({"cat": "ifeval", "task": p[:60], "ok": ok, "rules": res, "reply": t[:200]})
    return 100 * ok_n / len(H.IFEVAL), speeds


# ----------------------------------------------------------------------------- multi-hop web search
def web(query):
    q = str(query).lower()
    hits = [txt for keys, txt in H.WEB if all(k in q for k in keys)]
    return "\n".join(f"{i + 1}. {h}" for i, h in enumerate(hits)) if hits else "No results found."


def calc(expr):
    e = str(expr).replace(",", "").strip()
    if not re.fullmatch(r"[\d\s+\-*/().]+", e):
        return "ERROR: bad expression"
    try:
        return str(round(eval(e, {"__builtins__": {}}), 6))
    except Exception as ex:
        return f"ERROR: {ex}"


def run_search(port, log):
    ok_n, speeds = 0, []
    for q, groups, _min_hops, _needs_calc in H.SEARCH:
        msgs = [{"role": "system", "content": "You have tools: web_search and calculator. The facts asked about are not in your training data - search for them. You may search several times."},
                {"role": "user", "content": q}]
        searches, final = 0, ""
        for step in range(6):
            msg, sp = R.chat(port, msgs, 600, tools=[H.SEARCH_TOOL, H.CALC_TOOL])
            speeds.append(sp)
            calls = R.tool_calls(msg)
            if not calls:
                final = R.text_of(msg)
                break
            msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
                {"id": f"s{step}_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]})
            for i, (n, a) in enumerate(calls):
                a = a if isinstance(a, dict) else {}
                if n == "web_search":
                    searches += 1
                    res = web(a.get("query", ""))
                elif n == "calculator":
                    res = calc(a.get("expression", ""))
                else:
                    res = "ERROR: unknown tool"
                msgs.append({"role": "tool", "tool_call_id": f"s{step}_{i}", "content": res})
        ok = bool(final) and all(R.words_match(final.replace("$", ""), g) for g in groups)
        ok_n += ok
        log.append({"cat": "search", "task": q[:60], "ok": ok, "searches": searches, "reply": final[:200]})
    return 100 * ok_n / len(H.SEARCH), speeds


# ----------------------------------------------------------------------------- agent with real test runs
def run_tests_in(fs):
    tmp = Path(tempfile.mkdtemp(prefix="v100eval-"))
    try:
        tests = sorted(n for n in fs if Path(n).name.startswith("test_") and n.endswith(".py"))
        for name, content in fs.items():
            p = tmp / name
            p.parent.mkdir(parents=True, exist_ok=True)
            if name in tests:   # -I and the portable Python's ._pth do not put the project folder on sys.path
                content = "import sys as _s, os as _o\n_s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))\n" + content
            p.write_text(content, encoding="utf-8")
        if not tests:
            return True, "no tests found"
        out, ok = [], True
        for t in tests:
            try:
                r = subprocess.run([PY, "-I", "-B", t], cwd=tmp, capture_output=True, text=True, timeout=30,
                                   env={"PYTHONPATH": str(tmp), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
                ok &= r.returncode == 0
                out.append(f"{t}: {'PASSED' if r.returncode == 0 else 'FAILED'}\n{(r.stdout + r.stderr).strip()[-600:]}")
            except subprocess.TimeoutExpired:
                ok = False
                out.append(f"{t}: TIMEOUT")
        return ok, "\n".join(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def agent_tool(n, a, fs):
    if n == "list_files":
        return "\n".join(sorted(fs)) or "(empty)"
    if n == "read_file":
        return fs.get(str(a.get("path", "")).lstrip("./"), "ERROR: no such file")
    if n == "write_file":
        fs[str(a.get("path", "")).lstrip("./")] = str(a.get("content", ""))
        return "ok"
    if n == "run_tests":
        return run_tests_in(fs)[1]
    return "ERROR: unknown tool"


def agent_ok(kind, fs, orig):
    if kind == "tests_pass":
        if any(fs.get(k) != v for k, v in orig.items() if Path(k).name.startswith("test_")):
            return False                                   # editing the tests is cheating
        return run_tests_in(fs)[0]
    if kind == "report":
        return [l.strip() for l in fs.get("report.txt", "").splitlines() if l.strip()] == ["East: 100", "North: 150", "South: 100", "West: 0"]
    if kind == "config":
        try:
            d = json.loads(fs.get("config.json", ""))
        except Exception:
            return False
        return set(d) == {"name", "enabled", "retries_ms", "timeout"} and d["enabled"] is True and d["timeout"] == 2250 and d["retries_ms"] == [150, 300, 600, 1200]
    return False


def run_agent(port, log):
    ok_n, speeds = 0, []
    for instr, files, kind in H.AGENT:
        fs, steps, last = dict(files), 0, ""
        msgs = [{"role": "system", "content": "You are a coding agent working in a small project. Use the tools (list_files, read_file, write_file, run_tests) to complete the task. When finished, reply DONE."},
                {"role": "user", "content": instr}]
        try:
            for step in range(15):
                msg, sp = R.chat(port, msgs, 1500, tools=H.AGENT_TOOLS)
                speeds.append(sp)
                calls = R.tool_calls(msg)
                last = R.text_of(msg)
                if not calls:
                    break
                steps += 1
                msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
                    {"id": f"a{step}_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]})
                for i, (n, a) in enumerate(calls):
                    try:
                        res = agent_tool(n, a if isinstance(a, dict) else {}, fs)
                    except Exception as e:
                        res = f"ERROR: {e}"
                    msgs.append({"role": "tool", "tool_call_id": f"a{step}_{i}", "content": res})
            ok = agent_ok(kind, fs, files)
        except Exception as e:
            ok, last = False, f"[error] {e}"
        ok_n += ok
        log.append({"cat": "agent", "task": instr[:60], "ok": ok, "steps": steps, "reply": last[:160]})
    return 100 * ok_n / len(H.AGENT), speeds


# ----------------------------------------------------------------------------- vision
def run_vision(port, log):
    ok_n, speeds = 0, []
    for name, q, groups in H.VISION:
        b64 = base64.b64encode((HERE / "images" / f"{name}.png").read_bytes()).decode()
        msg, sp = R.chat(port, [{"role": "user", "content": [{"type": "text", "text": q + FINAL},
                                                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}], 800)
        speeds.append(sp)
        fin = last_line(R.text_of(msg))
        ok = all(R.words_match(fin, g) for g in groups)
        ok_n += ok
        log.append({"cat": "vision", "task": name, "ok": ok, "final": fin[:80]})
    return 100 * ok_n / len(H.VISION), speeds


# ----------------------------------------------------------------------------- long context (multi-needle, ~14k tokens)
def run_longctx(port, log, paragraphs=330):
    ok_n, speeds = 0, []
    topics = ["supply chains", "river ecology", "medieval trade", "battery chemistry", "urban planning", "bird migration"]
    for t in H.LONGCTX:
        lines = []
        spots = {int(paragraphs * f): n for f, n in zip((0.15, 0.5, 0.85), t["needles"])}
        for i in range(paragraphs):
            if i in spots:
                lines.append(spots[i])
            tp = topics[i % len(topics)]
            lines.append(f"Paragraph {i}: Researchers continued their review of {tp}, comparing archived notes from several sites and "
                         f"recording small differences in method, timing and scale in appendix {i} for the next meeting.")
        prompt = "\n".join(lines) + "\n\nQuestion: " + t["question"] + FINAL
        try:
            msg, sp = R.chat(port, [{"role": "user", "content": prompt}], 1200, timeout=1800)
            speeds.append(sp)
            fin = last_line(R.text_of(msg))
            ok = R.words_match(fin, t["answer"])
        except Exception as e:
            fin, ok = f"[error] {e}", False          # e.g. the configured context is too small
        ok_n += ok
        log.append({"cat": "longctx", "task": t["question"][:60], "ok": ok, "final": fin[:80]})
    return 100 * ok_n / len(H.LONGCTX), speeds


CATS = {"coding": run_coding, "reasoning": run_reasoning, "ifeval": run_ifeval, "search": run_search,
        "agent": run_agent, "vision": run_vision, "longctx": run_longctx}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--only", nargs="*", default=[], help="re-run just these categories and merge into the existing result")
    a = ap.parse_args()
    out = HERE / "results_hard" / f"{a.label}.json"
    if a.only and out.exists():
        old = json.loads(out.read_text(encoding="utf-8-sig"))
        for cat in a.only:
            s, sp = CATS[cat](a.port, log := [])
            old["scores"][cat] = round(s, 1)
            old["log"] = [x for x in old["log"] if x.get("cat") != cat] + log
            print(f"  {cat:9} {s:5.1f}  (re-run)", flush=True)
        old["overall"] = round(sum(old["scores"].values()) / len(CATS), 1)
        out.write_text(json.dumps(old, indent=1), encoding="utf-8")
        print(f"  overall {old['overall']}  -> {out}")
        return
    res = {"label": a.label, "suite": "hard", "scores": {}, "speed": {}, "log": []}
    all_sp = []
    for cat, fn in CATS.items():
        if cat in a.skip:
            res["scores"][cat] = 0.0          # a skipped capability (e.g. no vision) scores 0 in the overall
            continue
        t0 = time.time()
        try:
            s, sp = fn(a.port, res["log"])
        except Exception as e:
            s, sp = 0.0, []
            res["log"].append({"cat": cat, "error": str(e)})
        res["scores"][cat] = round(s, 1)
        all_sp += sp
        print(f"  {cat:9} {s:5.1f}   ({time.time() - t0:.0f}s)", flush=True)
    long = [x for x in all_sp if x["gen_tokens"] >= 64]
    res["speed"]["gen_tps"] = round(sum(x["gen_tps"] for x in long) / len(long), 1) if long else None
    pp = [x["prompt_tps"] for x in all_sp if x.get("prompt_tps")]
    res["speed"]["prompt_tps"] = round(max(pp), 0) if pp else None
    res["overall"] = round(sum(res["scores"].values()) / len(CATS), 1)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"  overall {res['overall']}  gen {res['speed']['gen_tps']} tok/s  -> {out}")


if __name__ == "__main__":
    main()
