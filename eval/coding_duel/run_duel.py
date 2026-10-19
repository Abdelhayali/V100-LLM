"""Coding duel: an agent (the model, with tools) solves 16 real coding tasks in a project folder on disk; hidden tests
(never shown to the model) grade the result, one point per test function.

  python run_duel.py --check                          prove the hidden tests: reference solutions pass, starting files fail
  python run_duel.py MODEL_ID:PRESET [--label NAME] [--tasks a,b] [--think]
                                                      start the model through the GUI launcher (port 7860) and run the duel

Results: results/<label>.json (per task: score, tests passed, steps, time, tokens, how the agent stopped) and
work/<label>/<task>/ (the files the agent left, for reading afterwards).
"""
import ast
import json
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import run_eval as R  # noqa: E402  (tool_calls, text_of)
from duel_tasks import TASKS  # noqa: E402

PY = sys.executable
PYFLAGS = ["-X", "utf8", "-I", "-B"]
GUI = "http://127.0.0.1:7860"
MAX_STEPS = 25
MAX_TOKENS = 6000
THINK_TOKENS = 32000   # Qwen3.8-27B often thinks for 12k+ tokens before a tool call

BOOT = '''import os, runpy, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
args = sys.argv[1:]
if args and args[0] == "-m":
    sys.argv = [args[1]] + args[2:]
    runpy.run_module(args[1], run_name="__main__", alter_sys=True)
elif args and args[0] == "-c":
    sys.argv = ["-c"] + args[2:]
    exec(compile(args[1], "<string>", "exec"), {"__name__": "__main__"})
else:
    sys.argv = args
    runpy.run_path(args[0], run_name="__main__")
'''
HIDDEN_HEAD = '''import os as _os, subprocess as _sp, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
def run_cli(args, timeout=60):
    return _sp.run([_sys.executable, "-X", "utf8", "-I", "-B", _os.path.join(_HERE, "_boot.py")] + list(args),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=_HERE)
'''
RUNONE = '''import os, sys, traceback
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
os.chdir(here)
import _hidden
try:
    getattr(_hidden, sys.argv[1])()
except BaseException as e:
    tb = traceback.extract_tb(e.__traceback__)
    print(f"{type(e).__name__}: {str(e)[:200]} (line {tb[-1].lineno if tb else '?'})")
    sys.exit(1)
'''

SYSTEM = ("You are an expert software engineer working as a coding agent in a project folder on the user's computer. "
          "Tools: list_files, read_file, write_file (creates folders as needed), run (runs a `python ...` command in the "
          "project folder: python file.py args, python -m package args, or python -c \"code\"; 60 s limit). Work "
          "carefully: read the existing files, write the code, then RUN it and test it yourself, including edge cases "
          "from the specification, and fix what fails. Hidden tests will check every requirement of the task, so "
          "follow the specification exactly. When you are completely done, reply with a short summary and no tool call.")
TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List all files in the project folder.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a text file.",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or overwrite a text file with the full new content.",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                                                     "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run", "description": "Run a python command in the project folder and return exit code, stdout and stderr.",
                                      "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]


# ----------------------------------------------------------------------------- project folder helpers
def write_files(root, files):
    for name, content in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")


def safe(root, rel):
    p = (root / str(rel).strip().lstrip("/\\")).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise ValueError("path outside the project folder")
    return p


def list_files(root):
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.name != "_boot.py":
            out.append(p.relative_to(root).as_posix())
    return out


def run_cmd(root, command, timeout=60):
    try:
        parts = shlex.split(command, posix=True)
    except ValueError as e:
        return f"ERROR: {e}"
    if not parts or parts[0] not in ("python", "python3", "py"):
        return "ERROR: only `python ...` commands are allowed"
    rest = parts[1:]
    while rest and rest[0] in ("-u", "-B", "-I", "-E", "-s"):
        rest = rest[1:]
    if not rest:
        return "ERROR: give a script, -m module or -c code"
    try:
        root = root.resolve()
        r = subprocess.run([PY] + PYFLAGS + [str(root / "_boot.py")] + rest, cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout} s"
    out = f"exit code {r.returncode}\n--- stdout ---\n{r.stdout[-3000:]}\n--- stderr ---\n{r.stderr[-3000:]}"
    return out


def tool(root, name, a):
    if name == "list_files":
        return "\n".join(list_files(root)) or "(empty)"
    if name == "read_file":
        p = safe(root, a.get("path", ""))
        return p.read_text(encoding="utf-8", errors="replace")[:20000] if p.is_file() else "ERROR: no such file"
    if name == "write_file":
        p = safe(root, a.get("path", ""))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(a.get("content", "")), encoding="utf-8", newline="\n")
        return f"wrote {p.relative_to(root).as_posix()} ({len(str(a.get('content', '')))} chars)"
    if name == "run":
        return run_cmd(root, str(a.get("command", "")))
    return "ERROR: unknown tool"


# ----------------------------------------------------------------------------- grading
def grade(project, t, gdir):
    """Copy the project to gdir, add the hidden tests, run every test_* function in its own process."""
    if gdir.exists():
        shutil.rmtree(gdir)
    shutil.copytree(project, gdir, ignore=shutil.ignore_patterns("__pycache__"))
    (gdir / "_boot.py").write_text(BOOT, encoding="utf-8")
    (gdir / "_hidden.py").write_text(HIDDEN_HEAD + t["hidden"], encoding="utf-8")
    (gdir / "_runone.py").write_text(RUNONE, encoding="utf-8")
    names = [n.name for n in ast.parse(t["hidden"]).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    res = {}
    for n in names:
        try:
            r = subprocess.run([PY] + PYFLAGS + [str(gdir / "_runone.py"), n], cwd=gdir, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60)
            res[n] = "ok" if r.returncode == 0 else ((r.stdout + r.stderr).strip().splitlines() or ["failed"])[-1][:240]
        except subprocess.TimeoutExpired:
            res[n] = "TIMEOUT"
    return res


def check():
    """Reference solutions must pass every hidden test; the untouched starting files must fail most of them."""
    tmp = HERE / "work" / "_check"
    bad = 0
    for t in TASKS:
        for which, files in (("ref", {**t["files"], **t["ref"]}), ("start", t["files"])):
            proj = tmp / f"{t['id']}-{which}"
            if proj.exists():
                shutil.rmtree(proj)
            proj.mkdir(parents=True)
            write_files(proj, files)
            res = grade(proj, t, tmp / f"{t['id']}-{which}-grade")
            ok = sum(v == "ok" for v in res.values())
            flag = ""
            if which == "ref" and ok != len(res):
                flag, bad = "  <-- REFERENCE FAILS", bad + 1
            if which == "start" and ok > len(res) // 2:
                flag = "  <-- starting files already pass most"
            print(f"{t['id']:18s} {which:5s} {ok}/{len(res)}{flag}")
            if which == "ref" and ok != len(res):
                for k, v in res.items():
                    if v != "ok":
                        print(f"      {k}: {v}")
    print("ALL REFERENCES PASS" if not bad else f"{bad} reference(s) fail")
    return bad == 0


# ----------------------------------------------------------------------------- model
def api(path, body=None, timeout=60):
    req = urllib.request.Request(GUI + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def start_model(mid, pid, budget=None):
    cat = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8-sig"))
    m = next(x for x in cat["models"] if x["id"] == mid)
    p = next(x for x in m["presets"] if x["id"] == pid)
    params = [{"flag": x[0], "value": x[1], "on": True} for x in p["params"]]
    if budget:   # cap thinking per reply; llama.cpp then closes the thinking block and the model acts
        params += [{"flag": "--reasoning-budget", "value": str(budget), "on": True},
                   {"flag": "--reasoning-budget-message", "value": "Enough thinking, act now.", "on": True}]
    r = api("/api/start", {"id": mid, "preset": pid, "kernel": p["kernel"], "params": params})
    if not r.get("ok"):
        raise SystemExit(f"start failed: {r.get('error')}")
    t0 = time.time()
    while time.time() - t0 < 1800:
        s = api("/api/status")
        if s["health"] == "ready":
            return m["name"], p["name"]
        if s["health"] == "stopped":
            raise SystemExit("server stopped:\n" + "\n".join(s["log"][-8:]))
        time.sleep(5)
    raise SystemExit("not ready after 30 min")


def chat(messages, think):
    body = {"messages": messages, "max_tokens": MAX_TOKENS if not think else THINK_TOKENS, "temperature": 0, "tools": TOOLS,
            "chat_template_kwargs": {"enable_thinking": think}}
    req = urllib.request.Request("http://127.0.0.1:8899/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read())
    tm = d.get("timings") or {}
    return d["choices"][0]["message"], d["choices"][0].get("finish_reason"), tm


def run_task(t, label, think):
    project = HERE / "work" / label / t["id"]
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True)
    write_files(project, t["files"])
    (project / "_boot.py").write_text(BOOT, encoding="utf-8")
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Task:\n{t['prompt']}\n\nFiles in the project folder now: {', '.join(list_files(project)) or '(none)'}"}]
    stats = {"steps": 0, "tool_calls": 0, "runs": 0, "writes": 0, "gen_tokens": 0, "prompt_tokens": 0, "stop": "max_steps"}
    t0 = time.time()
    trace = []
    for step in range(MAX_STEPS):
        try:
            msg, fin, tm = chat(msgs, think)
        except urllib.error.HTTPError as e:
            stats["stop"] = f"http {e.code}: {e.read().decode(errors='replace')[:200]}"
            break
        except Exception as e:
            stats["stop"] = f"error: {type(e).__name__}: {e}"[:200]
            break
        stats["steps"] += 1
        stats["gen_tokens"] += tm.get("predicted_n") or 0
        stats["prompt_tokens"] += tm.get("prompt_n") or 0
        calls = R.tool_calls(msg)
        if not calls:
            stats["stop"] = "done" if fin != "length" else "length"
            trace.append({"step": step, "final": R.text_of(msg)[:600]})
            break
        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
            {"id": f"c{step}_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]})
        for i, (n, a) in enumerate(calls):
            a = a if isinstance(a, dict) else {}
            try:
                res = tool(project, n, a)
            except Exception as e:
                res = f"ERROR: {e}"
            stats["tool_calls"] += 1
            stats["runs"] += n == "run"
            stats["writes"] += n == "write_file"
            trace.append({"step": step, "tool": n, "arg": (a.get("path") or a.get("command") or "")[:160], "result": res[:300]})
            msgs.append({"role": "tool", "tool_call_id": f"c{step}_{i}", "content": res})
    stats["seconds"] = round(time.time() - t0, 1)
    res = grade(project, t, HERE / "work" / label / f"_grade_{t['id']}")
    passed = sum(v == "ok" for v in res.values())
    return {"id": t["id"], "kind": t["kind"], "passed": passed, "total": len(res), "score": round(100 * passed / len(res), 1),
            "solved": passed == len(res), "tests": res, **stats, "trace": trace}


def main():
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
    target = next(a for a in sys.argv[1:] if not a.startswith("--") and ":" in a)
    mid, pid = target.split(":", 1)
    label = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--label=")), f"{mid}@{pid}")
    want = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--tasks=")), None)
    think = "--think" in sys.argv
    budget = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--budget=")), None)
    if think:
        label += "+think" + (f"{budget // 1024}k" if budget else "")
    name, pname = start_model(mid, pid, budget if think else None)
    print(f"== {name} / {pname}  (thinking {'on' if think else 'off'}{f', budget {budget} tokens' if think and budget else ''})", flush=True)
    out_path = HERE / "results" / f"{label}.json"
    out_path.parent.mkdir(exist_ok=True)
    done = {}
    if out_path.exists() and want is None:
        done = {r["id"]: r for r in json.loads(out_path.read_text(encoding="utf-8"))["tasks"]}
    results = []
    for t in TASKS:
        if want and t["id"] not in want:
            continue
        if t["id"] in done:
            results.append(done[t["id"]])
            continue
        r = run_task(t, label, think)
        results.append(r)
        print(f"  {t['id']:18s} {r['passed']:2d}/{r['total']:<2d} {r['score']:5.1f}%  steps {r['steps']:2d}  runs {r['runs']:2d}  "
              f"{r['seconds']:6.1f}s  {r['gen_tokens']:6d} tok  [{r['stop']}]", flush=True)
        summary = {"label": label, "model": name, "preset": pname, "think": think, "tasks": results}
        out_path.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    n = len(results)
    score = round(sum(r["score"] for r in results) / n, 1)
    tests = sum(r["passed"] for r in results), sum(r["total"] for r in results)
    print(f"  SCORE {score}%  solved {sum(r['solved'] for r in results)}/{n}  tests {tests[0]}/{tests[1]}  "
          f"time {round(sum(r['seconds'] for r in results) / 60, 1)} min", flush=True)


if __name__ == "__main__":
    main()
