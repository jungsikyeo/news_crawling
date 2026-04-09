from fastapi import APIRouter
from typing import Optional

from db.database import (
    get_connection, get_stats_by_date, get_stats_by_keyword,
    get_stats_by_portal, get_stats_by_publisher, get_stats_hourly,
    get_stats_article_hourly,
)

router = APIRouter()


@router.get("/daily")
def daily_stats(date_from: Optional[str] = None, date_to: Optional[str] = None,
                keyword: Optional[str] = None, portal: Optional[str] = None):
    conn = get_connection()
    rows = get_stats_by_date(conn, date_from, date_to, keyword, portal)
    conn.close()
    return [dict(r) for r in rows]


@router.get("/keyword")
def keyword_stats(date_from: Optional[str] = None, date_to: Optional[str] = None,
                  keyword: Optional[str] = None, portal: Optional[str] = None):
    conn = get_connection()
    rows = get_stats_by_keyword(conn, date_from, date_to, keyword, portal)
    conn.close()
    return [dict(r) for r in rows]


@router.get("/portal")
def portal_stats(date_from: Optional[str] = None, date_to: Optional[str] = None,
                 keyword: Optional[str] = None, portal: Optional[str] = None):
    conn = get_connection()
    rows = get_stats_by_portal(conn, date_from, date_to, keyword, portal)
    conn.close()
    return [dict(r) for r in rows]


@router.get("/publisher")
def publisher_stats(date_from: Optional[str] = None, date_to: Optional[str] = None,
                    keyword: Optional[str] = None, portal: Optional[str] = None):
    conn = get_connection()
    rows = get_stats_by_publisher(conn, date_from, date_to, keyword, portal)
    conn.close()
    return [dict(r) for r in rows]


@router.get("/hourly")
def hourly_stats(date_from: Optional[str] = None, date_to: Optional[str] = None,
                 keyword: Optional[str] = None, portal: Optional[str] = None):
    conn = get_connection()
    rows = get_stats_hourly(conn, date_from, date_to, keyword, portal)
    conn.close()
    return [dict(r) for r in rows]


@router.get("/article-hourly")
def article_hourly_stats(date_from: Optional[str] = None, date_to: Optional[str] = None,
                         keyword: Optional[str] = None, portal: Optional[str] = None):
    conn = get_connection()
    rows = get_stats_article_hourly(conn, date_from, date_to, keyword, portal)
    conn.close()
    return [dict(r) for r in rows]
