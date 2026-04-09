import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure backend package imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
