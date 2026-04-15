from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import csv
import io
import webbrowser
from datetime import datetime

from db.database import get_connection, get_news_list, get_news_count, reset_all_data, toggle_scrap, get_scrap_ids, get_scrapped_news

router = APIRouter()


@router.get("")
def list_news(keyword: Optional[str] = None, portal: Optional[str] = None,
              limit: int = 50, offset: int = 0,
              search: Optional[str] = None,
              date_from: Optional[str] = None, date_to: Optional[str] = None,
              sort_by: Optional[str] = "crawled_at", sort_order: Optional[str] = "desc",
              session_id: Optional[int] = None, history_id: Optional[int] = None):
    conn = get_connection()
    items = get_news_list(conn, keyword=keyword, portal=portal, limit=limit, offset=offset,
                          search=search, date_from=date_from, date_to=date_to,
                          sort_by=sort_by or "crawled_at", sort_order=sort_order or "desc",
                          session_id=session_id, history_id=history_id)
    total = get_news_count(conn, keyword=keyword, portal=portal, search=search,
                          date_from=date_from, date_to=date_to,
                          session_id=session_id, history_id=history_id)
    conn.close()
    return {
        "total": total,
        "items": [dict(row) for row in items],
    }


@router.get("/count")
def news_count():
    conn = get_connection()
    count = get_news_count(conn)
    conn.close()
    return {"count": count}


@router.get("/export")
def export_csv(keyword: Optional[str] = None, session_id: Optional[int] = None,
               history_id: Optional[int] = None,
               date_from: Optional[str] = None, date_to: Optional[str] = None):
    conn = get_connection()
    items = get_news_list(conn, keyword=keyword, limit=50000,
                          session_id=session_id, history_id=history_id,
                          date_from=date_from, date_to=date_to)
    conn.close()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "title", "published_at", "publisher", "url",
    ])
    writer.writeheader()
    for item in items:
        row = dict(item)
        writer.writerow({
            "title": row.get("title", ""),
            "published_at": row.get("published_at", ""),
            "publisher": row.get("publisher", ""),
            "url": row.get("url", ""),
        })

    output.seek(0)
    filename = f"newsdesk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class OpenUrlRequest(BaseModel):
    url: str


@router.post("/open-url")
def open_url(req: OpenUrlRequest):
    webbrowser.open(req.url)
    return {"status": "opened"}


@router.post("/scrap/{news_id}")
def scrap_toggle(news_id: int):
    conn = get_connection()
    is_scrapped = toggle_scrap(conn, news_id)
    conn.close()
    return {"scrapped": is_scrapped}


@router.get("/scraps")
def list_scraps(limit: int = 100, offset: int = 0):
    conn = get_connection()
    items = get_scrapped_news(conn, limit=limit, offset=offset)
    scrap_ids = get_scrap_ids(conn)
    conn.close()
    return {"items": [dict(row) for row in items], "scrap_ids": list(scrap_ids)}


@router.get("/scrap-ids")
def list_scrap_ids():
    conn = get_connection()
    ids = get_scrap_ids(conn)
    conn.close()
    return {"scrap_ids": list(ids)}


@router.delete("/reset")
def reset_data():
    conn = get_connection()
    reset_all_data(conn)
    conn.close()
    return {"status": "reset"}
