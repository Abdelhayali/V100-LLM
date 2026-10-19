"""PDF + code benchmark through the LocalAI Bridge app itself (same system prompt, tools and Python as the phone app).

Runs against an isolated test copy of the bridge (D:\\bridge-bench, port 8767: empty database, no memories, no Google,
no tunnel) that uses the model loaded by the V100-LLM launcher.

  python bench_bridge.py MODEL_ID:PRESET --label=NAME [--runs=2] [--only=pdf|code]

PDF tasks: English + Arabic documents. Automatic checks (file, pages, English words, Arabic letters, font embedded,
sent back to the user) plus page images in results/<label>/ for a visual check of the Arabic (connected letters,
right-to-left, no empty boxes). Code tasks: 4 tasks of the coding duel, graded by its hidden tests.
"""
import json
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "coding_duel"))
sys.path.insert(0, str(HERE.parent))
import run_duel as D  # noqa: E402  (start_model, grade, write_files)
from duel_tasks import TASKS as DUEL  # noqa: E402

BRIDGE = "http://127.0.0.1:8767"
WS = Path(r"D:\bridge-bench\workspace")
CFG = json.loads(Path(r"D:\bridge-bench\server\config.json").read_text(encoding="utf-8-sig"))
H = {"Authorization": "Bearer " + CFG["auth_token"], "Content-Type": "application/json"}
NOASK = " Do not ask me any questions: choose sensible defaults yourself."

PDF_TASKS = [
    {"id": "story", "file": "story.pdf", "pages": None, "en": 100, "ar": 300,
     "prompt": "Write a short English story (about 150-200 words) for children about a lost kitten who finds its way "
               "home, then translate the whole story into Arabic. Create a PDF named story.pdf in the folder {dir} "
               "with a title, the English story, and then the full Arabic translation. The Arabic must display "
               "correctly (connected letters, right to left). Send me the PDF."},
    {"id": "menu", "file": "menu.pdf", "pages": None, "en": 10, "ar": 20,
     "prompt": "Make a bilingual cafe price list as a PDF named menu.pdf in the folder {dir}: a title in English and "
               "Arabic, then a table with 6 drinks and 3 columns: English name, Arabic name, price in SAR. The Arabic "
               "must display correctly (connected letters, right to left). Send me the PDF."},
    {"id": "letter", "file": "letter.pdf", "pages": None, "en": 20, "ar": 200,
     "prompt": "Write a formal letter in Arabic inviting the employees of a company to a meeting about the new "
               "work-from-home policy next Sunday at 10 AM (at least 80 Arabic words), followed by a short English "
               "summary of the letter at the bottom. Save it as an A4 PDF named letter.pdf in the folder {dir}. The "
               "Arabic must display correctly (connected letters, right to left, right-aligned). Send me the PDF."},
    {"id": "water", "file": "water.pdf", "pages": 2, "en": 60, "ar": 250,
     "prompt": "Create a 2-page PDF named water.pdf in the folder {dir}. Page 1: a short English article 'Benefits "
               "of drinking water' with an introduction and 4 bullet points. Page 2: the full Arabic version of the "
               "same article, right-aligned. Put a page number at the bottom of each page. The Arabic must display "
               "correctly (connected letters, right to left). Send me the PDF."},
]
CODE_IDS = ["calc", "csv_report", "sudoku", "textstats_pkg"]
AR = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")
EN = re.compile(r"\b[A-Za-z]{2,}\b")


def api(method, path, body=None, timeout=60):
    req = urllib.request.Request(BRIDGE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=H, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


THINKING = "auto"


def chat(prompt, limit=900):
    """One request through the bridge, like the phone app; returns what happened."""
    sid = api("POST", "/api/sessions", {"model": ""})["id"]
    req = urllib.request.Request(f"{BRIDGE}/api/sessions/{sid}/chat", headers=H, method="POST",
                                 data=json.dumps({"content": prompt, "attachments": [], "auto_approve": True, "thinking": THINKING}).encode())
    t0, calls, sent, asked, rounds, gen, end, text = time.time(), [], [], 0, 0, 0, "timeout", ""
    try:
        with urllib.request.urlopen(req, timeout=limit) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                ev = json.loads(line[5:])
                t = ev.get("type")
                if t == "tool_call":
                    calls.append(ev.get("name"))
                elif t == "tool_result" and ev.get("name") == "send_file_to_user":
                    sent += [a.get("filename") or a.get("name") or "" for a in ev.get("attachments") or []] or [str(ev.get("output"))[:80]]
                elif t == "question_required":
                    asked += 1
                    opts = ev.get("options") or ["Yes"]
                    api("POST", f"/api/questions/{ev['id']}", {"answer": opts[0]})
                elif t == "stats":
                    rounds += 1
                    gen += ev.get("completion_tokens") or 0
                elif t == "delta":
                    text += ev.get("text") or ev.get("content") or ""
                elif t in ("done", "error"):
                    end = t if t == "done" else f"error: {str(ev.get('message') or ev)[:160]}"
                    break
                if time.time() - t0 > limit:
                    break
    except Exception as e:
        end = f"exception: {type(e).__name__}: {e}"[:160]
    return {"session": sid, "seconds": round(time.time() - t0, 1), "tool_calls": calls, "sent": sent, "asked": asked,
            "rounds": rounds, "gen_tokens": gen, "end": end, "reply": text[-400:]}


PDF_CHECK = r'''
import fitz, json, re, sys
p, out = sys.argv[1], sys.argv[2]
AR = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")
EN = re.compile(r"\b[A-Za-z]{2,}\b")
r = {"opens": False}
try:
    d = fitz.open(p)
    r["opens"] = True
    r["pages"] = d.page_count
    text = "".join(pg.get_text() for pg in d)
    r["en_words"] = len(EN.findall(text))
    r["ar_letters"] = len(AR.findall(text))
    r["ar_presentation_forms"] = len(re.findall(r"[\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    fonts = sorted({f[3] for pg in d for f in pg.get_fonts(full=True)})
    r["fonts"] = fonts
    r["embedded"] = any(f[1] != "n/a" and f[1] for pg in d for f in pg.get_fonts(full=True))
    imgs = []
    for i, pg in enumerate(d):
        if i >= 2:
            break
        f = f"{out}_p{i + 1}.png"
        pg.get_pixmap(dpi=80).save(f)
        imgs.append(f)
    r["images"] = imgs
except Exception as e:
    r["error"] = f"{type(e).__name__}: {e}"
print(json.dumps(r))
'''
VENV_PY = r"D:\LocalAI-Bridge-V100\server\.venv\Scripts\python.exe"


def grade_pdf(t, folder, outbase):
    import subprocess
    pdf = folder / t["file"]
    found = pdf if pdf.exists() else next(iter(sorted(folder.rglob("*.pdf"))), None)
    if found is None:
        found = next(iter(sorted(WS.rglob(t["file"]))), None)   # saved somewhere else in the workspace
    if found is None:
        return {"file": False, "points": 0, "checks": {}}
    r = subprocess.run([VENV_PY, "-X", "utf8", "-c", PDF_CHECK, str(found), str(outbase)], capture_output=True,
                       text=True, encoding="utf-8", timeout=120)
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        info = {"opens": False, "error": (r.stderr or r.stdout)[-300:]}
    checks = {
        "file_where_asked": found == pdf,
        "opens": info.get("opens", False),
        "pages_ok": info.get("opens", False) and (t["pages"] is None or info.get("pages") == t["pages"]),
        "english": info.get("en_words", 0) >= t["en"],
        "arabic": info.get("ar_letters", 0) >= t["ar"],
    }
    return {"file": True, "path": str(found), "points": sum(checks.values()), "checks": checks, **info}


def main():
    target = next(a for a in sys.argv[1:] if not a.startswith("--"))
    mid, pid = target.split(":", 1)
    label = next(a.split("=", 1)[1] for a in sys.argv if a.startswith("--label="))
    runs = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--runs=")), 2))
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    global THINKING
    THINKING = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--thinking=")), "auto")
    out = HERE / "results" / label
    out.mkdir(parents=True, exist_ok=True)
    name, pname = D.start_model(mid, pid)
    print(f"== {name} / {pname}  (thinking {THINKING})", flush=True)
    res = {"label": label, "model": name, "preset": pname, "thinking": THINKING, "pdf": [], "code": []}
    save = lambda: (HERE / "results" / f"{label}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    if only in (None, "pdf"):
        for t in PDF_TASKS:
            for k in range(runs):
                folder = WS / f"{t['id']}"
                if folder.exists():
                    shutil.rmtree(folder)
                folder.mkdir(parents=True)
                c = chat(t["prompt"].format(dir=str(folder)) + NOASK)
                g = grade_pdf(t, folder, out / f"{t['id']}_run{k + 1}")
                sent_pdf = any(t["file"] in s or s.lower().endswith(".pdf") for s in c["sent"])
                g["checks"]["sent_to_user"] = sent_pdf
                g["points"] = sum(g["checks"].values())
                res["pdf"].append({"id": t["id"], "run": k + 1, **c, **g})
                if g.get("file"):
                    shutil.copy(g["path"], out / f"{t['id']}_run{k + 1}.pdf")
                print(f"  pdf {t['id']:7s} run {k + 1}: {g['points']}/6  {c['seconds']:6.1f}s  rounds {c['rounds']:2d}  "
                      f"en {g.get('en_words', '-')}  ar {g.get('ar_letters', '-')}  pres {g.get('ar_presentation_forms', '-')}  "
                      f"fonts {','.join(g.get('fonts') or [])[:60]}  [{c['end']}]", flush=True)
                save()
    if only in (None, "code"):
        for t in [x for x in DUEL if x["id"] in CODE_IDS]:
            folder = WS / t["id"]
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True)
            D.write_files(folder, t["files"])
            prompt = (f"Work in the folder {folder} (it contains: {', '.join(D.list_files(folder)) or 'nothing yet'}). "
                      f"{t['prompt']} Save all files in that folder and test them with run_code before you finish." + NOASK)
            c = chat(prompt)
            g = D.grade(folder, t, out / f"_grade_{t['id']}")
            passed = sum(v == "ok" for v in g.values())
            res["code"].append({"id": t["id"], **c, "passed": passed, "total": len(g), "tests": g})
            print(f"  code {t['id']:14s} {passed}/{len(g)}  {c['seconds']:6.1f}s  rounds {c['rounds']:2d}  [{c['end']}]", flush=True)
            save()
    pts = sum(r["points"] for r in res["pdf"])
    code = sum(r["passed"] for r in res["code"]), sum(r["total"] for r in res["code"])
    print(f"  PDF auto {pts}/{6 * len(res['pdf'])}   CODE {code[0]}/{code[1]}   "
          f"time {round(sum(r['seconds'] for r in res['pdf'] + res['code']) / 60, 1)} min", flush=True)


if __name__ == "__main__":
    main()
