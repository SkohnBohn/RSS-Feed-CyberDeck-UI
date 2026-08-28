import json
import threading
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, render_template, request, url_for

import db
import scraper

try:
    import psutil as _psutil
    _net_prev = _psutil.net_io_counters()
    _net_prev_t = time.monotonic()
except ImportError:
    _psutil = None
    _net_prev = None
    _net_prev_t = None

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


def _base_ctx():
    return {
        "counts":        db.get_counts(),
        "collections":   db.get_collections(),
        "fetch_running": fetch_state["running"],
        "ui_theme":      db.get_setting("ui_theme", "classic"),
    }


# ── River (main feed) ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("river"))


@app.route("/river")
def river():
    last_opened = db.get_setting("last_opened_at")
    col_id      = request.args.get("collection", type=int)
    items       = db.get_river(last_opened_at=last_opened, collection_id=col_id)
    keywords    = db.get_keyword_filters()
    ctx         = _base_ctx()
    # Serialize articles for FUI JS panel
    _safe_keys = ("id","title","authors","journal","date_published","abstract",
                  "url","language","source","content_type","doi")
    articles_json = json.dumps([{k: a.get(k) for k in _safe_keys} for a in items])
    return render_template(
        "river.html",
        items=items,
        section="river",
        label="River",
        last_opened=last_opened,
        active_collection=col_id,
        keywords=keywords,
        articles_json=articles_json,
        **ctx,
    )


@app.route("/touch-session", methods=["POST"])
def touch_session():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db.set_setting("last_opened_at", now)
    return "", 204


@app.route("/api/sysmetrics")
def sysmetrics():
    global _net_prev, _net_prev_t
    if _psutil is None:
        return jsonify({"cpu": 0, "cpu_cores": [], "mem": 0, "net_sent_bps": 0, "net_recv_bps": 0})

    cpu_total = _psutil.cpu_percent(interval=None)
    cpu_cores = _psutil.cpu_percent(interval=None, percpu=True)
    mem       = _psutil.virtual_memory().percent
    net_now   = _psutil.net_io_counters()
    now_t     = time.monotonic()

    dt = now_t - _net_prev_t if _net_prev_t else 1.0
    net_sent_bps = max(0, (net_now.bytes_sent - _net_prev.bytes_sent) / dt) if _net_prev else 0
    net_recv_bps = max(0, (net_now.bytes_recv - _net_prev.bytes_recv) / dt) if _net_prev else 0
    _net_prev  = net_now
    _net_prev_t = now_t

    return jsonify({
        "cpu":          cpu_total,
        "cpu_cores":    cpu_cores,
        "mem":          mem,
        "net_sent_bps": net_sent_bps,
        "net_recv_bps": net_recv_bps,
    })


# ── Triage views ──────────────────────────────────────────────────────────────

VIEWS = {
    "flagged":     ("flagged",     "Flagged"),
    "interesting": ("interesting", "Interesting"),
    "read":        ("read",        "Read"),
}


@app.route("/<section>")
def view(section):
    if section not in VIEWS:
        return redirect(url_for("river"))
    status, label = VIEWS[section]
    col_id   = request.args.get("collection", type=int)
    articles = db.get_articles(status=status, collection_id=col_id)
    keywords = db.get_keyword_filters()
    ctx      = _base_ctx()
    _safe_keys = ("id","title","authors","journal","date_published","abstract",
                  "url","language","source","content_type","doi")
    articles_json = json.dumps([{k: a.get(k) for k in _safe_keys} for a in articles])
    return render_template(
        "inbox.html",
        articles=articles,
        articles_json=articles_json,
        section=section,
        label=label,
        active_collection=col_id,
        keywords=keywords,
        **ctx,
    )


# ── Item actions ──────────────────────────────────────────────────────────────

@app.route("/action/<int:article_id>/<action>", methods=["POST"])
def action(article_id, action):
    status_map = {
        "flag":        "flagged",
        "interesting": "interesting",
        "read":        "read",
        "unread":      "unread",
    }
    if action == "delete":
        db.delete_article(article_id)
    elif action in status_map:
        db.update_status(article_id, status_map[action])
    return "", 204


# ── Fetch ─────────────────────────────────────────────────────────────────────

@app.route("/fetch", methods=["POST"])
def fetch_now():
    if not fetch_state["running"]:
        threading.Thread(target=_do_fetch, kwargs={"days_back": 7}, daemon=True).start()
    return jsonify({"running": True})


@app.route("/fetch-status")
def fetch_status():
    return jsonify({"running": fetch_state["running"], "last_count": fetch_state["last_count"]})


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/settings")
def settings():
    ctx = _base_ctx()
    return render_template(
        "settings.html",
        section="settings",
        settings=db.get_all_settings(),
        feeds=db.get_feeds(),
        keyword_filters=db.get_keyword_filters(),
        saved=request.args.get("saved"),
        **ctx,
    )


@app.route("/settings/queries", methods=["POST"])
def save_queries():
    for key in ("query_openalex_en", "query_openalex_de", "query_base_en", "query_base_de"):
        value = request.form.get(key, "").strip()
        if value:
            db.set_setting(key, value)
    return redirect(url_for("settings", saved="1"))


@app.route("/settings/feeds/add", methods=["POST"])
def add_feed():
    name      = request.form.get("name", "").strip()
    url       = request.form.get("url", "").strip()
    lang      = request.form.get("lang", "en").strip()
    feed_type = request.form.get("feed_type", "rss").strip()
    col_id    = request.form.get("collection_id", "").strip() or None
    if name and url:
        db.add_feed(name, url, lang, feed_type, col_id)
    return redirect(url_for("settings"))


@app.route("/settings/feeds/<int:feed_id>/delete", methods=["POST"])
def delete_feed(feed_id):
    db.delete_feed(feed_id)
    return "", 204


# ── Collections ───────────────────────────────────────────────────────────────

@app.route("/settings/collections/add", methods=["POST"])
def add_collection():
    name = request.form.get("name", "").strip()
    if name:
        db.add_collection(name)
    return redirect(url_for("settings"))


@app.route("/settings/collections/<int:collection_id>/delete", methods=["POST"])
def delete_collection(collection_id):
    db.delete_collection(collection_id)
    return "", 204


# ── Keyword filters ───────────────────────────────────────────────────────────

@app.route("/settings/keywords/add", methods=["POST"])
def add_keyword():
    keyword = request.form.get("keyword", "").strip()
    mode    = request.form.get("mode", "emphasize").strip()
    if keyword:
        db.add_keyword_filter(keyword, mode)
    return redirect(url_for("settings"))


@app.route("/settings/keywords/<int:filter_id>/delete", methods=["POST"])
def delete_keyword(filter_id):
    db.delete_keyword_filter(filter_id)
    return "", 204


# ── Theme ─────────────────────────────────────────────────────────────────────

@app.route("/settings/theme", methods=["POST"])
def save_theme():
    theme = request.form.get("ui_theme", "classic")
    if theme in ("classic", "fui"):
        db.set_setting("ui_theme", theme)
    return redirect(url_for("settings"))


if __name__ == "__main__":
    app.run(debug=False, port=5000)
