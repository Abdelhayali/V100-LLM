"""Speech to text for meeting / voice notes with faster-whisper (large-v3-turbo), Arabic and English (auto-detected).

    python transcribe_worker.py --audio FILE --out RESULT.json [--device cpu|cuda] [--lang ar|en]

CPU (int8, the chat model stays on the GPU) by default; cuda (float16) when the bridge swapped the chat model out.
The result JSON: {"ok", "text", "language", "duration", "segments": [{"start", "end", "text"}], "seconds", "error"}.
"""
import argparse, json, os, sys, time
from pathlib import Path

MODEL = Path(os.environ.get("WHISPER_MODEL", Path(__file__).resolve().parent / "whisper"))   # setup-ocr.bat downloads it


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    ap.add_argument("--lang", default="")
    a = ap.parse_args()
    t0 = time.time()
    res = {"ok": False, "text": "", "language": "", "duration": 0, "segments": [], "error": ""}
    try:
        import av   # PyAV 15+ dropped open(metadata_errors=...), which faster-whisper 1.2 still passes
        _open = av.open
        av.open = lambda *x, **k: _open(*x, **{n: v for n, v in k.items() if n != "metadata_errors"})
        from faster_whisper import WhisperModel
        m = WhisperModel(str(MODEL), device=a.device, compute_type="float16" if a.device == "cuda" else "int8",
                         cpu_threads=max(1, (os.cpu_count() or 8) - 2))
        segs, info = m.transcribe(a.audio, language=a.lang or None, vad_filter=True, beam_size=5,
                                  condition_on_previous_text=False)
        out = []
        for s in segs:
            out.append({"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()})
            print(f"{s.end:7.1f}s", file=sys.stderr, flush=True)
        res.update(ok=True, segments=out, language=info.language, duration=round(info.duration, 1),
                   text="\n".join(x["text"] for x in out))
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"
    res["seconds"] = round(time.time() - t0, 1)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
