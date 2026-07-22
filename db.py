import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "surrealism.db"

DEFAULT_SETTINGS = {
    "query_openalex_en": "surrealism OR surrealist",
    "query_openalex_de": "Surrealismus OR surrealistisch",
    "query_base_en":     "surrealis*",
    "query_base_de":     "Surrealismus OR surrealistisch OR Surrealisten",
}

DEFAULT_FEEDS = [
    {"name": "Art History",                        "url": "https://onlinelibrary.wiley.com/feed/14678365/most-recent", "lang": "en"},
    {"name": "The Art Bulletin",                   "url": "https://www.tandfonline.com/feed/rss/rcab20",              "lang": "en"},
    {"name": "Oxford Art Journal",                 "url": "https://academic.oup.com/rss/site_5154/3072.xml",         "lang": "en"},
    {"name": "Word & Image",                       "url": "https://www.tandfonline.com/feed/rss/rwim20",             "lang": "en"},
    {"name": "Burlington Magazine",                "url": "https://www.burlington.org.uk/magazine/rss",              "lang": "en"},
    {"name": "Journal of Surrealism & the Americas","url": "https://scholarworks.wmich.edu/jsa/rss.xml",            "lang": "en"},
    {"name": "Zeitschrift für Kunstgeschichte",    "url": "https://www.degruyter.com/journal/key/zkg/rss",          "lang": "de"},
    {"name": "Kunstchronik",                       "url": "https://www.kunstchronik.de/feed/",                      "lang": "de"},
    {"name": "Kritische Berichte",                 "url": "https://kritische-berichte.de/feed/",                    "lang": "de"},
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                doi            TEXT UNIQUE,
                title          TEXT NOT NULL,
                authors        TEXT,
                journal        TEXT,
                year           INTEGER,
                date_published TEXT,
                abstract       TEXT,
                url            TEXT,
                language       TEXT,
                source         TEXT,
                date_fetched   TEXT DEFAULT (datetime('now')),
                status         TEXT DEFAULT 'unread'
            );

            CREATE TABLE IF NOT EXISTS fetch_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                fetch_time     TEXT DEFAULT (datetime('now')),
                articles_found INTEGER DEFAULT 0,
                status         TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS rss_feeds (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url  TEXT NOT NULL,
                lang TEXT DEFAULT 'en'
            );

            CREATE INDEX IF NOT EXISTS idx_status ON articles(status);
            CREATE INDEX IF NOT EXISTS idx_date   ON articles(date_published DESC);
        """)
    _seed_defaults()


def _seed_defaults():
    with get_conn() as conn:
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )
        count = conn.execute("SELECT COUNT(*) FROM rss_feeds").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO rss_feeds (name, url, lang) VALUES (:name, :url, :lang)",
                DEFAULT_FEEDS,
            )


# ── Articles ────────────────────────────────────────────────────────────────

def insert_article(doi, title, authors, journal, year, date_published,
                   abstract, url, language, source):
    if not title:
        return False
    with get_conn() as conn:
        try:
            conn.execute(
                """INSERT INTO articles
                   (doi, title, authors, journal, year, date_published,
                    abstract, url, language, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doi, title, authors, journal, year, date_published,
                 abstract, url, language, source),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_articles(status="unread"):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE status = ? ORDER BY date_published DESC, id DESC",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_counts():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM articles GROUP BY status"
        ).fetchall()
    counts = {"unread": 0, "flagged": 0, "interesting": 0, "read_later": 0}
    for row in rows:
        if row["status"] in counts:
            counts[row["status"]] = row["n"]
    return counts


def update_status(article_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE articles SET status = ? WHERE id = ?", (status, article_id))


def delete_article(article_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))


def get_last_fetch():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT fetch_time FROM fetch_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["fetch_time"] if row else None


def log_fetch(articles_found, status="ok"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO fetch_log (articles_found, status) VALUES (?, ?)",
            (articles_found, status),
        )


# ── Settings ────────────────────────────────────────────────────────────────

def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_all_settings():
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ── RSS feeds ────────────────────────────────────────────────────────────────

def get_feeds():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rss_feeds ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def add_feed(name, url, lang):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO rss_feeds (name, url, lang) VALUES (?, ?, ?)", (name, url, lang)
        )
        return cur.lastrowid


def delete_feed(feed_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM rss_feeds WHERE id = ?", (feed_id,))
