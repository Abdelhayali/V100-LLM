"""Language tutor: practise speaking English or Arabic with the PC's model.

  POST /api/tutor/turn       a conversation turn: natural reply + corrections + a better way to say it + score
  POST /api/tutor/sentence   a sentence to read aloud for the pronunciation drill
  POST /api/tutor/pronounce  compare what the recognizer heard with the target sentence: word marks + tips
Direct model calls (thinking off, fast), no chat history.
"""
import json
import re
from difflib import SequenceMatcher

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
LANG = {"en": "English", "ar": "Arabic (Modern Standard Arabic; write it with tashkeel)"}
# everyday situations for the pronunciation drill, so the sentences are ones people really use
SITUATIONS = ["ordering at a cafe", "asking for directions", "greeting a friend", "at the supermarket", "at the doctor",
              "making plans for the weekend", "talking about the weather", "at work with a colleague", "on the phone",
              "at a restaurant", "taking a taxi", "at the airport", "shopping for clothes", "at a hotel", "asking for help",
              "talking about family", "thanking someone", "apologizing for being late", "at the bank", "inviting someone home"]


class Turn(BaseModel):
    lang: str = "en"
    level: str = "intermediate"        # beginner | intermediate | advanced
    text: str
    history: list[dict] = []           # [{"role": "user"|"assistant", "content": ...}]
    topic: str = ""


class SentenceIn(BaseModel):
    lang: str = "en"
    level: str = "intermediate"
    topic: str = ""


class PronounceIn(BaseModel):
    lang: str = "en"
    target: str
    heard: str


def _json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


async def _llm(messages, max_tokens=900):
    from . import research
    return await research._llm(messages, max_tokens, think=False, temperature=0.4)


@router.post("/api/tutor/turn")
async def tutor_turn(b: Turn):
    lang = LANG.get(b.lang, "English")
    system = (f"You are a friendly {lang} conversation tutor for a {b.level} learner (their native language is Arabic"
              f"{'' if b.lang == 'ar' else ' or English'}). Keep the conversation going naturally"
              f"{' about ' + b.topic if b.topic else ''}: 1-3 short sentences, then a question. Reply with JSON only: "
              '{"reply": your answer in the target language, "corrections": [{"wrong": what they said, "right": correct form, '
              '"why": very short reason in English}], "better": a more natural way to say their whole sentence, '
              '"score": 0-10 for grammar and word choice}. corrections empty if there were no mistakes.')
    msgs = [{"role": "system", "content": system}] + [m for m in b.history[-12:] if m.get("role") in ("user", "assistant")]
    msgs.append({"role": "user", "content": b.text})
    d = _json(await _llm(msgs))
    return {"reply": str(d.get("reply") or "").strip(), "corrections": d.get("corrections") or [],
            "better": str(d.get("better") or "").strip(), "score": d.get("score")}


@router.post("/api/tutor/sentence")
async def tutor_sentence(b: SentenceIn):
    import random
    lang = LANG.get(b.lang, "English")
    topic = b.topic or random.choice(SITUATIONS)
    words = {"beginner": "5-9", "intermediate": "8-13", "advanced": "11-16"}.get(b.level, "8-13")
    raw = await _llm([{"role": "user", "content": f"Write one very common {lang} sentence that people really say every "
                       f"day, in this situation: {topic}. {words} words, natural spoken {lang} for a {b.level} learner, no rare "
                       "words or names, no quotes. If it naturally fits, include a sound that is hard for Arabic speakers"
                       + (" (p/b, v/f, th)" if b.lang == "en" else " (ح/ه, ع/ء, ق/ك, ض/د)")
                       + (". Write it in Modern Standard Arabic with full tashkeel" if b.lang == "ar" else "")
                       + ". Reply with only the sentence."}], 120)
    return {"sentence": raw.strip().strip('"“”')}


def _words(s: str) -> list[str]:
    s = re.sub(r"[ً-ْٰ]", "", s.lower())          # ignore tashkeel when comparing
    return re.findall(r"[\w']+", s)


@router.post("/api/tutor/pronounce")
async def tutor_pronounce(b: PronounceIn):
    t, h = _words(b.target), _words(b.heard)
    sm = SequenceMatcher(a=t, b=h)
    ok = [False] * len(t)
    for blk in sm.get_matching_blocks():
        for i in range(blk.a, blk.a + blk.size):
            ok[i] = True
    score = round(100 * sum(ok) / max(1, len(t)))
    missed = [w for w, good in zip(t, ok) if not good]
    tips = ""
    if missed:
        tips = (await _llm([{"role": "user", "content": f"A learner read this {LANG.get(b.lang, 'English')} sentence aloud: "
                             f"\"{b.target}\". Speech recognition heard: \"{b.heard}\". These words were not recognized: "
                             f"{', '.join(missed)}. In 2-4 short bullet points (in English), say how to pronounce those words "
                             "correctly (mouth position, stress, the sound that was probably wrong)."}], 300)).strip()
    return {"score": score, "words": [{"word": w, "ok": g} for w, g in zip(t, ok)], "missed": missed, "tips": tips}
