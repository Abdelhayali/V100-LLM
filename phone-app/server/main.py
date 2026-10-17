"""Headless launcher: python main.py  (prints the tunnel URL and a QR code in the console)."""
import io
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from bridge.runner import BridgeServer  # noqa: E402


def show_qr(srv: BridgeServer, url: str):
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(srv.pairing_payload())
    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)
    print("\n" + "=" * 60)
    print(f"  Tunnel URL: {url}")
    print("  Scan this QR in the Android app (Pair -> Scan QR):")
    print(buf.getvalue())
    print(f"  Or open http://127.0.0.1:{srv.port}/pair on this PC for a larger QR.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    srv = BridgeServer()
    srv.on_url_cb = lambda url: show_qr(srv, url)
    try:
        srv.start()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    try:
        while srv.running:
            time.sleep(1)
        print("Server stopped unexpectedly:", srv.error or "")
    except KeyboardInterrupt:
        srv.stop()
