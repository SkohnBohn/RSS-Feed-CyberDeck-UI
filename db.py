import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "surrealism.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                doi           TEXT UNIQUE,
                title         TEXT NOT NULL,
                authors       TEXT,
                journal       TEXT,
                year          INTEGER,
                date_published TEXT,
                abstract      TEXT,
                url           TEXT,
                language      TEXT,
                source        TEXT,
                date_fetched  TEXT DEFAULT (datetime('now')),
                status        TEXT DEFAULT 'unread'
            );

            CREATE TABLE IF NOT EXISTS fetch_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fetch_time      TEXT DEFAULT (datetime('now')),
                articles_found  INTEGER DEFAULT 0,
                status          TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_status ON articles(status);
            CREATE INDEX IF NOT EXISTS idx_date   ON articles(date_published DESC);
        """)


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
            return False  # duplicate DOI


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
        conn.execute(
            "UPDATE articles SET status = ? WHERE id = ?", (status, article_id)
        )


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
