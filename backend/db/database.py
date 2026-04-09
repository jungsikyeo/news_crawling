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

        CREATE TABLE IF NOT EXISTS scraps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id INTEGER NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            FOREIGN KEY (news_id) REFERENCES news(id)
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


def _resolve_relative_time(text: str) -> str:
    """'5분 전', '3시간 전', '1일 전' 등을 ISO datetime 문자열로 변환"""
    import re
    from datetime import timedelta
    now = datetime.now()
    m = re.match(r'(\d+)\s*분\s*전', text)
    if m:
        return (now - timedelta(minutes=int(m.group(1)))).strftime("%Y-%m-%d %H:%M")
    m = re.match(r'(\d+)\s*시간\s*전', text)
    if m:
        return (now - timedelta(hours=int(m.group(1)))).strftime("%Y-%m-%d %H:%M")
    m = re.match(r'(\d+)\s*일\s*전', text)
    if m:
        return (now - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d %H:%M")
    # "2026.04.09." 형식
    m = re.match(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', text)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return text


def insert_news(conn: sqlite3.Connection, title: str, url: str, description: str,
                publisher: str, published_at: str, keyword: str, portal: str) -> bool:
    norm = normalize_title(title)
    dup_id = find_duplicate(conn, title)
    now = datetime.now().isoformat()
    # 상대 시간을 절대 시간으로 변환
    if published_at:
        published_at = _resolve_relative_time(published_at)

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
                  portal: Optional[str] = None, limit: int = 100, offset: int = 0,
                  search: Optional[str] = None,
                  date_from: Optional[str] = None, date_to: Optional[str] = None):
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
    if search:
        query += " AND (n.title LIKE ? OR n.description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if date_from:
        query += " AND DATE(n.crawled_at) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND DATE(n.crawled_at) <= ?"
        params.append(date_to)
    query += " GROUP BY n.id ORDER BY n.crawled_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return conn.execute(query, params).fetchall()


def get_news_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]


def toggle_scrap(conn: sqlite3.Connection, news_id: int) -> bool:
    existing = conn.execute("SELECT id FROM scraps WHERE news_id = ?", (news_id,)).fetchone()
    if existing:
        conn.execute("DELETE FROM scraps WHERE news_id = ?", (news_id,))
        conn.commit()
        return False
    else:
        conn.execute("INSERT INTO scraps (news_id, created_at) VALUES (?, ?)",
                     (news_id, datetime.now().isoformat()))
        conn.commit()
        return True


def get_scrap_ids(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT news_id FROM scraps").fetchall()
    return {r[0] for r in rows}


def get_scrapped_news(conn: sqlite3.Connection, limit: int = 100, offset: int = 0):
    return conn.execute("""
        SELECT n.*, GROUP_CONCAT(DISTINCT np.portal) as portals,
               GROUP_CONCAT(DISTINCT np.url) as portal_urls
        FROM news n
        JOIN scraps s ON s.news_id = n.id
        LEFT JOIN news_portals np ON n.id = np.news_id
        GROUP BY n.id
        ORDER BY s.created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()


def reset_all_data(conn: sqlite3.Connection):
    conn.executescript("""
        DELETE FROM scraps;
        DELETE FROM news_portals;
        DELETE FROM news;
        DELETE FROM search_history;
    """)
    conn.commit()


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


def _stats_where(date_from: Optional[str] = None, date_to: Optional[str] = None,
                  keyword: Optional[str] = None, portal: Optional[str] = None,
                  table: str = "n"):
    clauses = []
    params = []
    if date_from:
        clauses.append(f"DATE({table}.crawled_at) >= ?")
        params.append(date_from)
    if date_to:
        clauses.append(f"DATE({table}.crawled_at) <= ?")
        params.append(date_to)
    if keyword:
        clauses.append(f"{table}.keyword = ?")
        params.append(keyword)
    if portal:
        clauses.append(f"EXISTS (SELECT 1 FROM news_portals np2 WHERE np2.news_id = {table}.id AND np2.portal = ?)")
        params.append(portal)
    where = " AND ".join(clauses)
    return (f" AND {where}" if where else ""), params


def get_stats_by_date(conn: sqlite3.Connection, date_from=None, date_to=None, keyword=None, portal=None):
    extra, params = _stats_where(date_from, date_to, keyword, portal, "news")
    return conn.execute(f"""
        SELECT DATE(crawled_at) as date, keyword, COUNT(*) as count
        FROM news
        WHERE 1=1 {extra}
        GROUP BY DATE(crawled_at), keyword
        ORDER BY date DESC
    """, params).fetchall()


def get_stats_by_publisher(conn: sqlite3.Connection, date_from=None, date_to=None, keyword=None, portal=None):
    extra, params = _stats_where(date_from, date_to, keyword, portal, "news")
    return conn.execute(f"""
        SELECT publisher, COUNT(*) as count
        FROM news
        WHERE publisher IS NOT NULL AND publisher != '' {extra}
        GROUP BY publisher
        ORDER BY count DESC
        LIMIT 30
    """, params).fetchall()


def get_stats_by_portal(conn: sqlite3.Connection, date_from=None, date_to=None, keyword=None, portal=None):
    extra, params = _stats_where(date_from, date_to, keyword, portal=None, table="n")
    portal_filter = ""
    if portal:
        portal_filter = " AND np.portal = ?"
        params.append(portal)
    return conn.execute(f"""
        SELECT np.portal, COUNT(*) as count
        FROM news_portals np
        JOIN news n ON n.id = np.news_id
        WHERE 1=1 {extra} {portal_filter}
        GROUP BY np.portal
        ORDER BY count DESC
    """, params).fetchall()


def get_stats_by_keyword(conn: sqlite3.Connection, date_from=None, date_to=None, keyword=None, portal=None):
    extra, params = _stats_where(date_from, date_to, keyword, portal, "news")
    return conn.execute(f"""
        SELECT keyword, COUNT(*) as count
        FROM news
        WHERE 1=1 {extra}
        GROUP BY keyword
        ORDER BY count DESC
    """, params).fetchall()


def get_stats_hourly(conn: sqlite3.Connection, date_from=None, date_to=None, keyword=None, portal=None):
    extra, params = _stats_where(date_from, date_to, keyword, portal, "news")
    return conn.execute(f"""
        SELECT strftime('%H', crawled_at) as hour, COUNT(*) as count
        FROM news
        WHERE 1=1 {extra}
        GROUP BY hour
        ORDER BY hour
    """, params).fetchall()


def get_stats_article_hourly(conn: sqlite3.Connection, date_from=None, date_to=None, keyword=None, portal=None):
    extra, params = _stats_where(date_from, date_to, keyword, portal, "news")
    return conn.execute(f"""
        SELECT strftime('%H', published_at) as hour, COUNT(*) as count
        FROM news
        WHERE published_at IS NOT NULL AND published_at LIKE '____-%' {extra}
        GROUP BY hour
        HAVING hour IS NOT NULL
        ORDER BY hour
    """, params).fetchall()
