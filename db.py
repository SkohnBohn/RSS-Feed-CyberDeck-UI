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
    {"name": "Art History",                         "url": "https://onlinelibrary.wiley.com/feed/14678365/most-recent", "lang": "en", "feed_type": "rss"},
    {"name": "The Art Bulletin",                    "url": "https://www.tandfonline.com/feed/rss/rcab20",              "lang": "en", "feed_type": "rss"},
    {"name": "Oxford Art Journal",                  "url": "https://academic.oup.com/rss/site_5154/3072.xml",         "lang": "en", "feed_type": "rss"},
    {"name": "Word & Image",                        "url": "https://www.tandfonline.com/feed/rss/rwim20",             "lang": "en", "feed_type": "rss"},
    {"name": "Burlington Magazine",                 "url": "https://www.burlington.org.uk/magazine/rss",              "lang": "en", "feed_type": "rss"},
    {"name": "Journal of Surrealism & the Americas","url": "https://scholarworks.wmich.edu/jsa/rss.xml",             "lang": "en", "feed_type": "rss"},
    {"name": "Zeitschrift für Kunstgeschichte",     "url": "https://www.degruyter.com/journal/key/zkg/rss",          "lang": "de", "feed_type": "rss"},
    {"name": "Kunstchronik",                        "url": "https://www.kunstchronik.de/feed/",                      "lang": "de", "feed_type": "rss"},
    {"name": "Kritische Berichte",                  "url": "https://kritische-berichte.de/feed/",                    "lang": "de", "feed_type": "rss"},
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
                status         TEXT DEFAULT 'unread',
                content_type   TEXT DEFAULT 'article',
                media_url      TEXT,
                thumbnail_url  TEXT,
                collection_id  INTEGER
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
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                url           TEXT NOT NULL,
                lang          TEXT DEFAULT 'en',
                feed_type     TEXT DEFAULT 'rss',
                collection_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS collections (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS keyword_filters (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                mode    TEXT DEFAULT 'emphasize'
            );

            CREATE INDEX IF NOT EXISTS idx_status ON articles(status);
            CREATE INDEX IF NOT EXISTS idx_date   ON articles(date_published DESC);
        """)
    _migrate_db()
    _seed_defaults()


def _migrate_db():
    """Add columns introduced after the initial schema, then normalise status values."""
    with get_conn() as conn:
        art_cols = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
        for col, defn in [
            ("content_type",  "TEXT DEFAULT 'article'"),
            ("media_url",     "TEXT"),
            ("thumbnail_url", "TEXT"),
            ("collection_id", "INTEGER"),
        ]:
            if col not in art_cols:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {col} {defn}")

        feed_cols = {row[1] for row in conn.execute("PRAGMA table_info(rss_feeds)").fetchall()}
        for col, defn in [
            ("feed_type",     "TEXT DEFAULT 'rss'"),
            ("collection_id", "INTEGER"),
        ]:
            if col not in feed_cols:
                conn.execute(f"ALTER TABLE rss_feeds ADD COLUMN {col} {defn}")

        # read_later → read (renamed status)
        conn.execute("UPDATE articles SET status = 'read' WHERE status = 'read_later'")


def _seed_defaults():
    with get_conn() as conn:
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )
        count = conn.execute("SELECT COUNT(*) FROM rss_feeds").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO rss_feeds (name, url, lang, feed_type) VALUES (:name, :url, :lang, :feed_type)",
                DEFAULT_FEEDS,
            )


# ── Articles / River ─────────────────────────────────────────────────────────

def insert_article(doi, title, authors, journal, year, date_published,
                   abstract, url, language, source,
                   content_type="article", media_url=None, thumbnail_url=None,
                   collection_id=None):
    if not title:
        return False
    with get_conn() as conn:
        try:
            conn.execute(
                """INSERT INTO articles
                   (doi, title, authors, journal, year, date_published,
                    abstract, url, language, source,
                    content_type, media_url, thumbnail_url, collection_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doi, title, authors, journal, year, date_published,
                 abstract, url, language, source,
                 content_type, media_url, thumbnail_url, collection_id),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_river(last_opened_at=None, collection_id=None):
    """All unread items, split into new (since last visit) and seen."""
    where = "status = 'unread'"
    params = []
    if collection_id:
        where += " AND collection_id = ?"
        params.append(collection_id)

    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT *,
                CASE WHEN ? IS NULL OR date_fetched > ? THEN 1 ELSE 0 END AS is_new
                FROM articles
                WHERE {where}
                ORDER BY is_new DESC, date_fetched DESC, date_published DESC, id DESC""",
            [last_opened_at, last_opened_at] + params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_articles(status="unread", collection_id=None):
    where = "status = ?"
    params = [status]
    if collection_id:
        where += " AND collection_id = ?"
        params.append(collection_id)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM articles WHERE {where} ORDER BY date_published DESC, id DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_counts():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM articles GROUP BY status"
        ).fetchall()
    counts = {"unread": 0, "flagged": 0, "interesting": 0, "read": 0}
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


def log_fetch(articles_found, status="ok"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO fetch_log (articles_found, status) VALUES (?, ?)",
            (articles_found, status),
        )


# ── Settings ─────────────────────────────────────────────────────────────────

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


# ── RSS / source feeds ────────────────────────────────────────────────────────

def get_feeds():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rss_feeds ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def add_feed(name, url, lang, feed_type="rss", collection_id=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO rss_feeds (name, url, lang, feed_type, collection_id) VALUES (?, ?, ?, ?, ?)",
            (name, url, lang, feed_type, collection_id or None),
        )
        return cur.lastrowid


def delete_feed(feed_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM rss_feeds WHERE id = ?", (feed_id,))


# ── Collections ───────────────────────────────────────────────────────────────

def get_collections():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM collections ORDER BY sort_order, name"
        ).fetchall()
        return [dict(r) for r in rows]


def add_collection(name):
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO collections (name) VALUES (?)", (name,))
        return cur.lastrowid


def delete_collection(collection_id):
    with get_conn() as conn:
        conn.execute("UPDATE articles  SET collection_id = NULL WHERE collection_id = ?", (collection_id,))
        conn.execute("UPDATE rss_feeds SET collection_id = NULL WHERE collection_id = ?", (collection_id,))
        conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))


# ── Keyword filters ───────────────────────────────────────────────────────────

def get_keyword_filters():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM keyword_filters ORDER BY mode, keyword"
        ).fetchall()
        return [dict(r) for r in rows]


def add_keyword_filter(keyword, mode="emphasize"):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO keyword_filters (keyword, mode) VALUES (?, ?)", (keyword, mode)
        )
        return cur.lastrowid


def delete_keyword_filter(filter_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM keyword_filters WHERE id = ?", (filter_id,))
