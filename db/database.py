import sqlite3
import os
from datetime import datetime
from typing import Optional


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "news.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT,
            publisher TEXT,
            published_at TEXT,
            keyword TEXT NOT NULL,
            portal TEXT NOT NULL,
            crawled_at TEXT NOT NULL,
            title_normalized TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS news_portals (
            news_id INTEGER NOT NULL,
            portal TEXT NOT NULL,
            url TEXT NOT NULL,
            PRIMARY KEY (news_id, portal),
            FOREIGN KEY (news_id) REFERENCES news(id)
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keywords TEXT NOT NULL,
            portals TEXT NOT NULL,
            interval_minutes INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_news_title_norm ON news(title_normalized);
        CREATE INDEX IF NOT EXISTS idx_news_keyword ON news(keyword);
        CREATE INDEX IF NOT EXISTS idx_news_portal ON news(portal);
        CREATE INDEX IF NOT EXISTS idx_news_crawled_at ON news(crawled_at);
        CREATE INDEX IF NOT EXISTS idx_news_publisher ON news(publisher);
    """)
    conn.commit()
    conn.close()


def normalize_title(title: str) -> str:
    import re
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip().lower()
    return title


def find_duplicate(conn: sqlite3.Connection, title: str) -> Optional[int]:
    from difflib import SequenceMatcher
    norm = normalize_title(title)
    cursor = conn.execute(
        "SELECT id, title_normalized FROM news WHERE title_normalized LIKE ?",
        (f"%{norm[:20]}%",)
    )
    for row in cursor.fetchall():
        ratio = SequenceMatcher(None, norm, row["title_normalized"]).ratio()
        if ratio >= 0.75:
            return row["id"]
    return None


def insert_news(conn: sqlite3.Connection, title: str, url: str, description: str,
                publisher: str, published_at: str, keyword: str, portal: str) -> bool:
    norm = normalize_title(title)
    dup_id = find_duplicate(conn, title)
    now = datetime.now().isoformat()

    if dup_id:
        existing = conn.execute(
            "SELECT portal FROM news_portals WHERE news_id = ? AND portal = ?",
            (dup_id, portal)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO news_portals (news_id, portal, url) VALUES (?, ?, ?)",
                (dup_id, portal, url)
            )
            conn.commit()
        return False

    cursor = conn.execute(
        """INSERT INTO news (title, url, description, publisher, published_at,
           keyword, portal, crawled_at, title_normalized)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, url, description, publisher, published_at, keyword, portal, now, norm)
    )
    news_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO news_portals (news_id, portal, url) VALUES (?, ?, ?)",
        (news_id, portal, url)
    )
    conn.commit()
    return True


def get_news_list(conn: sqlite3.Connection, keyword: Optional[str] = None,
                  portal: Optional[str] = None, limit: int = 100, offset: int = 0):
    query = """
        SELECT n.*, GROUP_CONCAT(DISTINCT np.portal) as portals,
               GROUP_CONCAT(DISTINCT np.url) as portal_urls
        FROM news n
        LEFT JOIN news_portals np ON n.id = np.news_id
        WHERE 1=1
    """
    params = []
    if keyword:
        query += " AND n.keyword = ?"
        params.append(keyword)
    if portal:
        query += " AND EXISTS (SELECT 1 FROM news_portals np2 WHERE np2.news_id = n.id AND np2.portal = ?)"
        params.append(portal)
    query += " GROUP BY n.id ORDER BY n.crawled_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return conn.execute(query, params).fetchall()


def get_news_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]


def save_search_history(conn: sqlite3.Connection, keywords: str, portals: str,
                        interval_minutes: int):
    conn.execute(
        "INSERT INTO search_history (keywords, portals, interval_minutes, created_at) VALUES (?, ?, ?, ?)",
        (keywords, portals, interval_minutes, datetime.now().isoformat())
    )
    conn.commit()


def get_search_history(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM search_history ORDER BY created_at DESC"
    ).fetchall()


def delete_search_history(conn: sqlite3.Connection, history_id: int):
    conn.execute("DELETE FROM search_history WHERE id = ?", (history_id,))
    conn.commit()


def get_stats_by_date(conn: sqlite3.Connection):
    return conn.execute("""
        SELECT DATE(crawled_at) as date, keyword, COUNT(*) as count
        FROM news
        GROUP BY DATE(crawled_at), keyword
        ORDER BY date DESC
    """).fetchall()


def get_stats_by_publisher(conn: sqlite3.Connection):
    return conn.execute("""
        SELECT publisher, COUNT(*) as count
        FROM news
        WHERE publisher IS NOT NULL AND publisher != ''
        GROUP BY publisher
        ORDER BY count DESC
        LIMIT 30
    """).fetchall()


def get_stats_by_portal(conn: sqlite3.Connection):
    return conn.execute("""
        SELECT portal, COUNT(*) as count
        FROM news_portals
        GROUP BY portal
        ORDER BY count DESC
    """).fetchall()


def get_stats_by_keyword(conn: sqlite3.Connection):
    return conn.execute("""
        SELECT keyword, COUNT(*) as count
        FROM news
        GROUP BY keyword
        ORDER BY count DESC
    """).fetchall()


def get_stats_hourly(conn: sqlite3.Connection):
    return conn.execute("""
        SELECT strftime('%H', crawled_at) as hour, COUNT(*) as count
        FROM news
        GROUP BY hour
        ORDER BY hour
    """).fetchall()
