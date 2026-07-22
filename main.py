"""
Desktop entry point — opens the dashboard in a native app window.
Run with:  python3 main.py
"""
import threading
import time

import webview

from app import app as flask_app


def _run_flask():
    flask_app.run(port=5000, use_reloader=False, threaded=True)


if __name__ == "__main__":
    t = threading.Thread(target=_run_flask, daemon=True)
    t.start()
    time.sleep(1)  # let Flask bind before webview opens

    window = webview.create_window(
        title="Surrealism Papers Dashboard",
        url="http://localhost:5000",
        width=1280,
        height=820,
        min_size=(900, 600),
    )
    webview.start()
