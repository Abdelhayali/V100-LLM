"""Offline neural voices for read-aloud (Piper): a small local HTTP server that keeps the voices loaded.

    python tts_server.py [--port 8781]        POST /tts {"text": ..., "voice": "en_US-amy-medium"} -> audio/wav
                                              GET  /voices -> [{"id", "lang", "name", "quality"}]

Started by the bridge on first use; listens on 127.0.0.1 only. Voices: ocr/piper/*.onnx (setup-ocr.bat).
"""
import argparse, io, json, os, threading, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIR = Path(os.environ.get("PIPER_VOICES", Path(__file__).resolve().parent / "piper"))
_voices: dict = {}
_lock = threading.Lock()


def voices():
    out = []
    for f in sorted(DIR.glob("*.onnx")):
        lang, _, rest = f.stem.partition("-")
        name, _, quality = rest.rpartition("-")
        out.append({"id": f.stem, "lang": lang, "name": name.replace("_", " ").title(), "quality": quality})
    return out


def voice(vid: str):
    with _lock:
        if vid not in _voices:
            from piper import PiperVoice
            _voices[vid] = PiperVoice.load(str(DIR / f"{vid}.onnx"))
        return _voices[vid]


def synth(text: str, vid: str) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voice(vid).synthesize_wav(text, w)
    return buf.getvalue()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/voices":
            self.send(200, json.dumps(voices()).encode())
        elif self.path == "/health":
            self.send(200, b'{"ok": true}')
        else:
            self.send(404, b"{}")

    def do_POST(self):
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            vid = str(b.get("voice") or "")
            if not (DIR / f"{vid}.onnx").exists():
                return self.send(404, json.dumps({"error": f"no voice {vid}"}).encode())
            text = str(b.get("text") or "").strip()[:8000]
            if not text:
                return self.send(400, b'{"error": "empty text"}')
            self.send(200, synth(text, vid), "audio/wav")
        except Exception as e:
            self.send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8781)
    a = ap.parse_args()
    for v in voices():                       # warm up: the first synthesis of each voice is the slow one
        try:
            synth("ok", v["id"])
        except Exception:
            pass
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
