import threading

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, render_template, url_for

import db
import scraper

app = Flask(__name__)
db.init_db()

fetch_state = {"running": False, "last_count": None}


def _do_fetch(days_back=1):
    fetch_state["running"] = True
    try:
        n = scraper.run_fetch(days_back=days_back)
        fetch_state["last_count"] = n
    finally:
        fetch_state["running"] = False


def _initial_fetch():
    with db.get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    if count == 0:
        _do_fetch(days_back=7)


threading.Thread(target=_initial_fetch, daemon=True).start()

scheduler = BackgroundScheduler()
scheduler.add_job(_do_fetch, "interval", hours=24, kwargs={"days_back": 1})
scheduler.start()


VIEWS = {
    "inbox":       ("unread",      "Inbox"),
    "flagged":     ("flagged",     "Flagged"),
    "interesting": ("interesting", "Interesting"),
    "read-later":  ("read_later",  "Read Later"),
}


@app.route("/")
def index():
    return redirect(url_for("view", section="inbox"))


@app.route("/<section>")
def view(section):
    if section not in VIEWS:
        return redirect(url_for("view", section="inbox"))
    status, label = VIEWS[section]
    articles = db.get_articles(status=status)
    counts = db.get_counts()
    return render_template(
        "inbox.html",
        articles=articles,
        section=section,
        label=label,
        counts=counts,
        fetch_running=fetch_state["running"],
    )


@app.route("/action/<int:article_id>/<action>", methods=["POST"])
def action(article_id, action):
    status_map = {
        "flag":        "flagged",
        "interesting": "interesting",
        "read_later":  "read_later",
        "unread":      "unread",
    }
    if action == "delete":
        db.delete_article(article_id)
    elif action in status_map:
        db.update_status(article_id, status_map[action])
    return "", 204


@app.route("/fetch", methods=["POST"])
def fetch_now():
    if not fetch_state["running"]:
        threading.Thread(target=_do_fetch, kwargs={"days_back": 7}, daemon=True).start()
    return jsonify({"running": True})


@app.route("/fetch-status")
def fetch_status():
    return jsonify({
        "running": fetch_state["running"],
        "last_count": fetch_state["last_count"],
    })


if __name__ == "__main__":
    app.run(debug=False, port=5000)
