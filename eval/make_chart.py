"""
Builds the leaderboard from results/*.json:
  results/leaderboard.html   bar chart (Artificial-Analysis style) + score/size/speed table
  results/leaderboard.png    the same chart as an image (rendered with Microsoft Edge, if installed)
  results/leaderboard.md     table for GitHub
"""
import html
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import sys

HERE = Path(__file__).resolve().parent
BASIC = "--basic" in sys.argv            # v1 suite; the default is v2 (hard)
RES = HERE / ("results" if BASIC else "results_hard")
TITLE = "V100-LLM Intelligence Index (basic v1)" if BASIC else "V100-LLM Hard Index (v2)"
SUBTITLE = ("Single Tesla V100 16 GB · coding, chat &amp; reasoning, instruction following, web search (tools), agent tasks, vision"
            if BASIC else "Single Tesla V100 16 GB · hard coding, multi-step reasoning, multi-rule instructions, multi-hop search, "
                          "agent tasks with tests, vision, long context")
CATS = ([("coding", "Coding"), ("chat", "Chat & reasoning"), ("ifeval", "Instructions"), ("search", "Web search"),
         ("agent", "Agent"), ("vision", "Vision")] if BASIC else
        [("coding", "Coding"), ("reasoning", "Reasoning"), ("ifeval", "Instructions"), ("search", "Web search"),
         ("agent", "Agent"), ("vision", "Vision"), ("longctx", "Long context")])
# soft pastel per kernel family, like the reference chart
COLORS = {"pxa": "#f6c7b6", "fastmtp": "#b9d3f5", "llamacpp": "#bfe3c4", "prism": "#d9c8f2", "strata": "#f7d9a8", "exllamav3": "#f4c2d7"}
DARK = {"pxa": "#c9785c", "fastmtp": "#4f86d1", "llamacpp": "#3f9a52", "prism": "#8a63c9", "strata": "#c98a1f", "exllamav3": "#c24f80"}


def load():
    rows = []
    for f in sorted(RES.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8-sig"))
        if "overall" in d:
            rows.append(d)
    return sorted(rows, key=lambda d: d["overall"], reverse=True)


SHORT = {"minicpm-v4.7-35b": "MiniCPM-V 4.7 IQ3_XS", "qwen3.8-27b-pxq3": "Qwen3.8-27B PXQ3", "saluki-27b": "Saluki 27B (MTP)",
         "bonsai-heretic-27b": "Bonsai-2 27B Heretic", "nemotron-bolt-74b": "Nemotron-3.5 Bolt 74B", "fusion4-35b-pxq2": "PXA-Fusion4 35B",
         "ornith-35b-pxq2": "Ornith-1.5 35B", "strata-flash-next": "Strata IQ2_XS", "strata-flash-next@q2_0": "Strata Q2_0", "strata-flash-next@coder-iq1m": "Strata Coder IQ1_M", "hauhau-qwen3.8-27b": "HauhauCS IQ3_XS",
         "qwen3.8-27b-exl3": "Qwen3.8-27B EXL3 3.0bpw", "hauhau-qwen3.8-27b-q2kp": "HauhauCS Q2_K_P", "huihui-qwen3.8-27b-gsq": "Huihui abliterated GSQ IQ3_S", "ista-qwen3.8-27b-gsq": "ISTA-DASLab GSQ IQ3_S", "orca-qwen3.8-27b-gsq": "OrcaRouter Uncensored GSQ",
         "unsloth-qwen3.8-27b-iq3s": "Qwen3.8-27B Unsloth UD-IQ3_S",
         "minicpm-v4.7-35b-q3mix": "MiniCPM-V 4.7 Q3 mix", "minicpm-v4.7-35b-uncensored": "MiniCPM-V 4.7 Uncensored",
         "minicpm-v4.7-35b-crack": "MiniCPM-V 4.7 CRACK"}


def short(d):
    return SHORT.get(d["label"]) or SHORT.get(d.get("model_id", ""), d.get("model", d["label"]).split(" (")[0])


def svg_chart(rows, w=1180, h=520):
    n = max(len(rows), 1)
    left, right, top, bottom = 90, 20, 70, 175
    pw, ph = w - left - right, h - top - bottom
    bw = pw / n * 0.72
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Segoe UI, Arial, sans-serif">',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
           f'<text x="20" y="32" font-size="22" font-family="Georgia, serif" fill="#111">{TITLE}</text>',
           f'<text x="20" y="54" font-size="12" fill="#666">{SUBTITLE} · temperature 0, thinking off</text>']
    for g in (25, 50, 75, 100):
        y = top + ph * (1 - g / 100)
        out.append(f'<line x1="{left}" x2="{w - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e7eb" stroke-dasharray="3 3"/>')
        out.append(f'<text x="{left - 8}" y="{y + 4:.1f}" font-size="11" fill="#9aa1ab" text-anchor="end">{g}</text>')
    for i, d in enumerate(rows):
        k = d.get("kernel", "llamacpp")
        x = left + pw / n * i + (pw / n - bw) / 2
        bh = ph * d["overall"] / 100
        y = top + ph - bh
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{COLORS.get(k, "#ddd")}"/>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{y + bh / 2 + 5:.1f}" font-size="14" font-weight="600" fill="#222" text-anchor="middle">{d["overall"]:.0f}</text>')
        tps = d.get("speed", {}).get("gen_tps")
        if tps:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 6:.1f}" font-size="10" fill="#666" text-anchor="middle">{tps:.0f} t/s</text>')
        out.append(f'<circle cx="{x + bw / 2:.1f}" cy="{top + ph + 14}" r="5" fill="{DARK.get(k, "#888")}"/>')
        lx, ly = x + bw / 2 + 4, top + ph + 28
        name = html.escape(short(d))
        out.append(f'<text transform="translate({lx:.1f},{ly}) rotate(-40)" font-size="12" fill="#333" text-anchor="end">{name}</text>')
    lx = w - right - 5
    for j, (k, c) in enumerate(reversed(list(DARK.items()))):
        out.append(f'<circle cx="{lx - 90}" cy="{top - 28 + 0}" r="0"/>')
    leg = ' · '.join(f'<tspan fill="{DARK[k]}">●</tspan> {k}' for k in DARK)
    out.append(f'<text x="{w - right}" y="32" font-size="12" fill="#444" text-anchor="end">kernel: {leg}</text>')
    out.append("</svg>")
    return "\n".join(out)


def context_of(d):
    """Context of the preset the model was scored with, from catalog.json (e.g. '262k')."""
    try:
        cat = json.loads((HERE.parent / "catalog.json").read_text(encoding="utf-8-sig"))
        m = next(x for x in cat["models"] if x["id"] == d.get("model_id"))
        p = next((x for x in m["presets"] if x["name"].startswith(d.get("preset") or "\0")), m["presets"][0])
        v = next(x[1] for x in p["params"] if x[0] in ("-c", "--ctx-size", "--max-context", "--max-seq-len"))
        return "262k" if int(v) == 262144 else f"{int(v) // 1024}k"
    except (StopIteration, KeyError, ValueError, OSError):
        return ""


CTX_FLAGS = ("-c", "--ctx-size", "--max-context", "--max-seq-len")


def max_context_of(d):
    """Largest context of any of the model's presets in catalog.json: the most it was tested to run with on the V100."""
    try:
        cat = json.loads((HERE.parent / "catalog.json").read_text(encoding="utf-8-sig"))
        m = next(x for x in cat["models"] if x["id"] == d.get("model_id"))
        v = max(int(x[1]) for p in m["presets"] for x in p["params"] if x[0] in CTX_FLAGS)
        return "262k" if v == 262144 else f"{v // 1024}k"
    except (StopIteration, KeyError, ValueError, OSError):
        return ""


def table(rows, md=False):
    head = (["#", "Model", "Kernel", "Size (GB)", "Context (scored)", "Max context on V100", "Gen tok/s", "Prompt tok/s (short)"]
            + [c[1] for c in CATS] + ["Overall"])
    lines = []
    for i, d in enumerate(rows, 1):
        sp = d.get("speed", {})
        sc = d["scores"]

        lines.append([str(i), d.get("model", d["label"]), d.get("kernel", ""), f'{d.get("size_gb") or ""}', context_of(d), max_context_of(d),
                      f'{sp.get("gen_tps") or ""}', f'{int(sp["prompt_tps"]) if sp.get("prompt_tps") else ""}']
                     + [f'{sc[c]:.0f}' if c in sc else "–" for c, _ in CATS] + [f'**{d["overall"]:.1f}**' if md else f'{d["overall"]:.1f}'])
    if md:
        return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(l) + " |" for l in lines])
    th = "".join(f"<th>{html.escape(x)}</th>" for x in head)
    tb = "".join("<tr>" + "".join(f"<td>{html.escape(x)}</td>" for x in l) + "</tr>" for l in lines)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>"


def main():
    rows = load()
    svg = svg_chart(rows)
    (RES / "leaderboard.svg").write_text(svg, encoding="utf-8")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>V100-LLM Leaderboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{margin:0;padding:16px;background:#fff;color:#1d2330;font:14px/1.45 "Segoe UI",system-ui,sans-serif}}
.chart{{max-width:1180px}} table{{border-collapse:collapse;margin-top:16px;font-size:13px}}
th,td{{border-bottom:1px solid #e5e7eb;padding:5px 9px;text-align:right}} th:nth-child(2),td:nth-child(2){{text-align:left}}
th{{background:#f6f7f9}} p{{color:#667085;max-width:1100px}}</style></head><body>
<div class="chart">{svg}</div>
{table(rows)}
<p>Scores are pass rates (0-100) per category; Overall is their mean. Every model ran on one Tesla V100-SXM2-16GB with its
recommended V100-LLM preset, temperature 0, thinking off. Tasks are in eval/tasks.py and are graded by code (unit tests,
exact answers, checked tool calls and final agent state) - no LLM judge. Gen tok/s is the mean over replies of 64+ tokens.</p>
</body></html>"""
    (RES / "leaderboard.html").write_text(page, encoding="utf-8")
    (RES / "leaderboard.md").write_text("# V100-LLM leaderboard\n\n![leaderboard](leaderboard.png)\n\n" + table(rows, md=True) + "\n", encoding="utf-8")
    edge = next((p for p in [shutil.which("msedge"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"] if p and os.path.exists(p)), None)
    if edge:
        tmp = RES / "_chart.html"
        tmp.write_text(f'<!doctype html><html><body style="margin:0">{svg}</body></html>', encoding="utf-8")
        t0 = time.time()
        subprocess.run([edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={RES / '_edge'}", "--window-size=1180,520",
                        f"--screenshot={RES / 'leaderboard.png'}", tmp.as_uri()], capture_output=True, timeout=60)
        # msedge.exe hands off to a background process and returns before the PNG is written
        png = RES / "leaderboard.png"
        while time.time() - t0 < 30 and (not png.exists() or png.stat().st_mtime < t0 - 2):
            time.sleep(0.5)
        time.sleep(2)
        tmp.unlink(missing_ok=True)
        shutil.rmtree(RES / "_edge", ignore_errors=True)
    print(f"leaderboard: {len(rows)} models -> {RES / 'leaderboard.html'}")


if __name__ == "__main__":
    main()
