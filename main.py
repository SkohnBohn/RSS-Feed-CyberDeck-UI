"""
Desktop entry point — opens the dashboard in a native app window.
Run with:  python3 main.py
"""
import socket
import threading
import time

import webview

from app import app as flask_app


def _run_flask():
    flask_app.run(port=5000, use_reloader=False, threaded=True)


def _wait_for_flask(port=5000, timeout=15):
    """Poll until Flask is actually accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


if __name__ == "__main__":
    t = threading.Thread(target=_run_flask, daemon=True)
    t.start()

    if not _wait_for_flask():
        print("Error: Flask did not start within 15 seconds.")
        raise SystemExit(1)

    window = webview.create_window(
        title="Surrealism Papers Dashboard",
        url="http://localhost:5000",
        width=1280,
        height=820,
        min_size=(900, 600),
    )
    webview.start()
