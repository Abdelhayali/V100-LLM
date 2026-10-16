"""Repairs UTF-8 text that was read as cp1252 and saved again (double-encoded), in place."""
import sys
from pathlib import Path

for name in sys.argv[1:]:
    p = Path(name)
    s = p.read_bytes().decode("utf-8-sig")
    if not any(ch in s for ch in "ÂÃâ"):
        print("clean:", p)
        continue
    out = bytearray()
    for ch in s:
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            out += ch.encode("latin-1") if ord(ch) < 256 else ch.encode("utf-8")
    p.write_text(out.decode("utf-8"), encoding="utf-8", newline="")
    print("fixed:", p)
