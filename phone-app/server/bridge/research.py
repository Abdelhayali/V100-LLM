"""Deep-research agent: "research X" runs in the background on the PC and ends with a report with numbered sources.

  plan queries -> web search -> read each page and take notes for the question -> (deep: find gaps, search again)
  -> write the report with [n] citations and a source list

The report goes to its own chat ("🔎 ...") and to workspace/research/<date>-<slug>.md, and the phone gets a notification.
The model runs with thinking off for the many small reading steps and with a little thinking for the plan and report.
"""
import asyncio
import json
import re
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import db, schedules, tools
from .config import config, llm_api_base

router = APIRouter()
DEPTH = {"quick": (3, 6, 1), "normal": (5, 10, 1), "deep": (7, 16, 2)}   # queries, pages, extra gap rounds
runs: dict[str, dict] = {}


class ResearchIn(BaseModel):
    question: str
    depth: str = "normal"          # quick | normal | deep


async def _llm(messages, max_tokens=1500, think=False, temperature=0.3) -> str:
    from . import app as A
    model = await A.pick_model(None)
    payload = {"model": model, "stream": False, "max_tokens": max_tokens + (2048 if think else 0),
               "temperature": temperature, "messages": messages,
               "chat_template_kwargs": {"enable_thinking": think}}
    if think:
        payload["reasoning_budget_tokens"] = 2048
    async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10)) as c:
        r = await c.post(llm_api_base() + "/chat/completions", headers=A.llm_headers(), json=payload)
        r.raise_for_status()
    return A._strip_think(r.json()["choices"][0]["message"].get("content") or "").strip()


def _json_list(text: str) -> list[str]:
    m = re.search(r"\[.*\]", text, re.S)
    try:
        return [str(x).strip() for x in json.loads(m.group(0)) if str(x).strip()] if m else []
    except Exception:
        return [l.strip(" -•\t\"") for l in text.splitlines() if l.strip(" -•\t\"")][:8]


def _search(q: str) -> list[tuple[str, str]]:
    out = []
    for block in tools.web_search(q, max_results=6).split("\n\n"):
        lines = block.splitlines()
        if len(lines) >= 2 and lines[1].startswith("http"):
            out.append((lines[0].split("] ", 1)[-1], lines[1].strip()))
    return out


async def _run(rid: str, question: str, depth: str):
    st = runs[rid]
    nq, npages, gaps = DEPTH.get(depth, DEPTH["normal"])
    sid = st["session_id"]

    def step(msg):
        st["progress"] = msg
        st["log"].append(time.strftime("%H:%M:%S ") + msg)

    try:
        step("planning the searches")
        plan = await _llm([{"role": "system", "content": "You plan web research. Reply with only a JSON list of search queries."},
                           {"role": "user", "content": f"Question: {question}\n\nWrite {nq} different web search queries that "
                            "together cover it (facts, recent data, expert views, counter-arguments). Use the question's "
                            "language and also English when that finds better sources."}], 600, think=True)
        queries = _json_list(plan)[:nq] or [question]
        seen, sources, notes = set(), [], []

        async def gather(qs):
            for q in qs:
                step(f"searching: {q}")
                for title, url in await asyncio.to_thread(_search, q):
                    host = re.sub(r"^www\.", "", url.split("/")[2]) if url.count("/") >= 2 else url
                    if url in seen or sum(1 for s in sources if host in s["url"]) >= 2 or len(sources) >= npages:
                        continue
                    seen.add(url)
                    step(f"reading {len(sources) + 1}/{npages}: {title[:60]}")
                    try:
                        page = await asyncio.to_thread(tools.fetch_url, url, 9000)
                    except Exception:
                        continue
                    note = await _llm([{"role": "system", "content": "You take research notes. Be factual and concise."},
                                       {"role": "user", "content": f"Research question: {question}\n\nSource: {title}\n{url}\n\n"
                                        f"{page[:9000]}\n\nWrite up to 8 short bullet points with the facts, numbers, dates "
                                        "and claims from this source that matter for the question. If it is irrelevant or "
                                        "empty, reply only: IRRELEVANT"}], 700)
                    if note and "IRRELEVANT" not in note[:20].upper():
                        sources.append({"title": title, "url": url})
                        notes.append(f"[{len(sources)}] {title} ({url})\n{note}")
                if len(sources) >= npages:
                    break

        await gather(queries)
        for _ in range(gaps):
            if len(sources) >= npages:
                break
            step("checking what is still missing")
            more = await _llm([{"role": "system", "content": "You review research. Reply with only a JSON list."},
                               {"role": "user", "content": f"Question: {question}\n\nNotes so far:\n" + "\n\n".join(notes)[:12000] +
                                "\n\nWhat important part is still missing or contradictory? Give 1-3 new search queries "
                                "as a JSON list, or [] if nothing is missing."}], 400)
            qs = _json_list(more)[:3]
            if not qs:
                break
            await gather(qs)

        if not notes:
            raise RuntimeError("no usable sources were found (web search may be blocked or offline)")
        step(f"writing the report from {len(sources)} sources")
        report = await _llm([{"role": "system", "content": "You write careful research reports in Markdown."},
                             {"role": "user", "content": f"Question: {question}\n\nResearch notes from numbered sources:\n\n" +
                              "\n\n".join(notes)[:40000] + "\n\nWrite the report in the question's language: a short "
                              "answer first, then sections with the details, then open questions or disagreements between "
                              "sources. Cite sources inline as [n] after each claim. Do not invent facts that are not in the "
                              "notes. Do not add a source list (it is added automatically)."}], 3500, think=True)
        report += "\n\n## Sources\n" + "\n".join(f"{i + 1}. [{s['title']}]({s['url']})" for i, s in enumerate(sources))
        out_dir = Path(config["workspace"]) / "research"
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^\w]+", "-", question.lower())[:50].strip("-") or "report"
        f = out_dir / f"{time.strftime('%Y-%m-%d-%H%M')}-{slug}.md"
        f.write_text(f"# {question}\n\n" + report, encoding="utf-8")
        att = tools.share_file(f)
        db.add_message(sid, "assistant", report, attachments=[att])
        st.update(status="done", file=str(f), sources=len(sources))
        step("done")
        schedules.notify("research", "🔎 Research ready: " + question[:60], f"{len(sources)} sources · tap to read", sid)
    except Exception as e:
        st.update(status="error", error=f"{type(e).__name__}: {e}")
        step("failed: " + st["error"])
        db.add_message(sid, "assistant", f"The research could not be finished: {st['error']}")
        schedules.notify("research", "🔎 Research failed: " + question[:60], st["error"][:200], sid)
    finally:
        st["ended"] = time.time()


@router.post("/api/research")
async def research_start(b: ResearchIn):
    q = b.question.strip()
    if not q:
        raise HTTPException(400, "empty question")
    if any(r["status"] == "running" for r in runs.values()):
        raise HTTPException(409, "a research run is already going; wait for it to finish")
    sess = db.create_session("🔎 " + q[:60], "")
    db.add_message(sess["id"], "user", f"Research ({b.depth}): {q}")
    rid = sess["id"]
    runs[rid] = {"id": rid, "session_id": rid, "question": q, "depth": b.depth, "status": "running",
                 "progress": "starting", "log": [], "started": time.time(), "ended": 0, "sources": 0, "error": ""}
    asyncio.create_task(_run(rid, q, b.depth))
    return runs[rid]


@router.get("/api/research")
async def research_list():
    return sorted(runs.values(), key=lambda r: -r["started"])
