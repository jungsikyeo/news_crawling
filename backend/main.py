import sys
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure backend package imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 파일 로깅 설정 — 설치 루트의 logs/ 폴더에 생성
if getattr(sys, 'frozen', False):
    # exe: resources/backend/NewsDesk.exe → 설치 루트는 3단계 위
    _install_root = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
    _log_dir = os.path.join(_install_root, "logs")
else:
    _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(_log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_log_dir, "newsdesk.log"), encoding="utf-8"),
    ],
)

from db.database import init_db
from scheduler import CrawlScheduler
from api.crawl import router as crawl_router
from api.news import router as news_router
from api.stats import router as stats_router
from api.history import router as history_router

scheduler = CrawlScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown()


app = FastAPI(title="NewsDesk API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl_router, prefix="/api/crawl", tags=["crawl"])
app.include_router(news_router, prefix="/api/news", tags=["news"])
app.include_router(stats_router, prefix="/api/stats", tags=["stats"])
app.include_router(history_router, prefix="/api/history", tags=["history"])

# Serve React build if exists
# PyInstaller 번들 환경에서는 _MEIPASS 기준, 개발 환경에서는 상대 경로
if getattr(sys, 'frozen', False):
    frontend_dist = os.path.join(sys._MEIPASS, "frontend", "dist")
else:
    frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
