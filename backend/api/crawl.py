from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional

from db.database import get_connection, save_search_history

router = APIRouter()


class CrawlStartRequest(BaseModel):
    keywords: List[str]
    portals: List[str]
    interval_minutes: int
    start_date: Optional[str] = ""


class CrawlRunOnceRequest(BaseModel):
    keywords: List[str]
    portals: List[str]
    start_date: Optional[str] = ""


@router.post("/start")
def start_crawl(req: CrawlStartRequest, request: Request):
    scheduler = request.app.state.scheduler
    conn = get_connection()
    save_search_history(conn, ",".join(req.keywords), ",".join(req.portals), req.interval_minutes)
    conn.close()
    scheduler.start_crawling(req.keywords, req.portals, req.interval_minutes, start_date=req.start_date or "")
    return {"status": "started", "keywords": req.keywords, "portals": req.portals}


@router.post("/stop")
def stop_crawl(request: Request):
    scheduler = request.app.state.scheduler
    scheduler.stop_crawling()
    return {"status": "stopped"}


@router.post("/run-once")
def run_once(req: CrawlRunOnceRequest, request: Request):
    scheduler = request.app.state.scheduler
    conn = get_connection()
    save_search_history(conn, ",".join(req.keywords), ",".join(req.portals), 0)
    conn.close()
    scheduler.run_once(req.keywords, req.portals, start_date=req.start_date or "")
    return {"status": "running"}


@router.get("/status")
def crawl_status(request: Request):
    scheduler = request.app.state.scheduler
    job = scheduler.scheduler.get_job("news_crawl") if hasattr(scheduler, 'scheduler') else None
    return {
        "is_running": scheduler.is_running or scheduler.is_run_once,
        "crawling_active": job is not None,
        "last_run": scheduler.last_run.isoformat() if scheduler.last_run else None,
        "last_error": scheduler.last_error,
        "errors": scheduler.errors,
        "new_count": scheduler.new_count,
        "total_count": scheduler.total_count,
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
    }
