"""Speech-to-text server for the live meeting assistant: keeps faster-whisper (large-v3-turbo, int8 on the CPU) loaded so
each 20-second piece is transcribed in seconds. Listens on 127.0.0.1 only.

    POST /stt   body = audio file (wav)   ?lang=ar|en (optional)   -> {"text", "language", "segments": [...]}
"""
import argparse, io, json, os, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MODEL = Path(os.environ.get("WHISPER_MODEL", Path(__file__).resolve().parent / "whisper"))
_model = None
_lock = threading.Lock()


def model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(str(MODEL), device="cpu", compute_type="int8", cpu_threads=max(1, (os.cpu_count() or 8) - 4))
    return _model


def stt(audio: bytes, lang: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio)
        path = f.name
    try:
        with _lock:                  # one piece at a time (they arrive in order)
            segs, info = model().transcribe(path, language=lang or None, vad_filter=True, beam_size=3,
                                            condition_on_previous_text=False)
            out = [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()} for s in segs]
        return {"text": " ".join(s["text"] for s in out).strip(), "language": info.language, "segments": out}
    finally:
        os.unlink(path)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self.send(200, {"ok": True}) if self.path == "/health" else self.send(404, {})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/stt":
            return self.send(404, {})
        try:
            audio = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            lang = (parse_qs(u.query).get("lang") or [""])[0]
            self.send(200, stt(audio, lang))
        except Exception as e:
            self.send(500, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    import av   # PyAV 15+ dropped open(metadata_errors=...), which faster-whisper 1.2 still passes
    _open = av.open
    av.open = lambda *x, **k: _open(*x, **{n: v for n, v in k.items() if n != "metadata_errors"})
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8782)
    a = ap.parse_args()
    model()                          # load before saying "ready"
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
