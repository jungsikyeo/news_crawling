import logging
import threading
from datetime import datetime
from typing import List, Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from crawlers.naver import NaverCrawler
from crawlers.daum import DaumCrawler
from crawlers.nate import NateCrawler
from db.database import get_connection, insert_news, create_crawl_session, complete_crawl_session

logger = logging.getLogger(__name__)

CRAWLERS = {
    "naver": NaverCrawler,
    "daum": DaumCrawler,
    "nate": NateCrawler,
}


class CrawlScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self._lock = threading.Lock()
        self.is_running = False
        self.is_run_once = False
        self.last_run: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.errors: List[str] = []
        self.new_count = 0
        self.total_count = 0
        self._on_complete: Optional[Callable] = None

    def set_callback(self, callback: Callable):
        self._on_complete = callback

    def _crawl_job(self, keywords: List[str], portals: List[str], start_date: str = "",
                   mode: str = "OR", history_id: int = 0):
        with self._lock:
            if self.is_running:
                logger.info("이전 크롤링이 아직 진행 중입니다.")
                return
            self.is_running = True

        self.errors = []
        try:
            conn = get_connection()
            session_id = create_crawl_session(conn, history_id) if history_id else None
            new_count = 0
            total_count = 0

            for portal_name in portals:
                crawler_cls = CRAWLERS.get(portal_name)
                if not crawler_cls:
                    logger.warning(f"알 수 없는 포탈: {portal_name}")
                    continue

                crawler = crawler_cls()

                if mode == "AND":
                    combined = " ".join(keywords)
                    try:
                        articles = crawler.search_all_pages(combined, max_pages=3, start_date=start_date)
                        total_count += len(articles)
                        for article in articles:
                            is_new = insert_news(
                                conn,
                                title=article["title"],
                                url=article["url"],
                                description=article.get("description", ""),
                                publisher=article.get("publisher", ""),
                                published_at=article.get("published_at", ""),
                                keyword=combined,
                                portal=portal_name,
                                session_id=session_id,
                            )
                            if is_new:
                                new_count += 1
                    except Exception as e:
                        err_msg = f"[{portal_name}] AND 검색 '{combined}': {e}"
                        self.errors.append(err_msg)
                        logger.error(f"크롤링 에러: {err_msg}")
                else:
                    for keyword in keywords:
                        try:
                            articles = crawler.search_all_pages(keyword, max_pages=3, start_date=start_date)
                            total_count += len(articles)
                            for article in articles:
                                is_new = insert_news(
                                    conn,
                                    title=article["title"],
                                    url=article["url"],
                                    description=article.get("description", ""),
                                    publisher=article.get("publisher", ""),
                                    published_at=article.get("published_at", ""),
                                    keyword=keyword,
                                    portal=portal_name,
                                    session_id=session_id,
                                )
                                if is_new:
                                    new_count += 1
                        except Exception as e:
                            err_msg = f"[{portal_name}] '{keyword}': {e}"
                            self.errors.append(err_msg)
                            logger.error(f"크롤링 에러: {err_msg}")

            if session_id:
                complete_crawl_session(conn, session_id, new_count, total_count)
            conn.close()
            self.new_count = new_count
            self.total_count = total_count
            self.last_run = datetime.now()
            self.last_error = "; ".join(self.errors) if self.errors else None
            logger.info(f"크롤링 완료: 총 {total_count}건 수집, 신규 {new_count}건, 에러 {len(self.errors)}건")

        except Exception as e:
            self.last_error = str(e)
            self.errors.append(str(e))
            logger.error(f"크롤링 작업 에러: {e}")
        finally:
            with self._lock:
                self.is_running = False
            if self._on_complete:
                try:
                    self._on_complete()
                except Exception:
                    pass

    def start_crawling(self, keywords: List[str], portals: List[str],
                       interval_minutes: int, start_date: str = "",
                       mode: str = "OR", history_id: int = 0):
        self.stop_crawling()

        # 즉시 실행
        thread = threading.Thread(
            target=self._crawl_job, args=(keywords, portals, start_date, mode, history_id), daemon=True
        )
        thread.start()

        # 주기적 실행 등록
        self.scheduler.add_job(
            self._crawl_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            args=[keywords, portals, start_date, mode, history_id],
            id="news_crawl",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"크롤링 스케줄 시작: {interval_minutes}분 간격, mode={mode}")

    def stop_crawling(self):
        try:
            self.scheduler.remove_job("news_crawl")
        except Exception:
            pass

    def run_once(self, keywords: List[str], portals: List[str], start_date: str = "",
                 mode: str = "OR", history_id: int = 0):
        self.is_run_once = True
        thread = threading.Thread(
            target=self._run_once_job, args=(keywords, portals, start_date, mode, history_id), daemon=True
        )
        thread.start()

    def _run_once_job(self, keywords: List[str], portals: List[str], start_date: str = "",
                      mode: str = "OR", history_id: int = 0):
        """즉시수집 전용 — 스케줄 크롤링과 독립적으로 실행"""
        self.errors = []
        try:
            conn = get_connection()
            session_id = create_crawl_session(conn, history_id) if history_id else None
            new_count = 0
            total_count = 0

            for portal_name in portals:
                crawler_cls = CRAWLERS.get(portal_name)
                if not crawler_cls:
                    continue
                crawler = crawler_cls()

                if mode == "AND":
                    combined = " ".join(keywords)
                    try:
                        articles = crawler.search_all_pages(combined, max_pages=3, start_date=start_date)
                        total_count += len(articles)
                        for article in articles:
                            is_new = insert_news(
                                conn,
                                title=article["title"],
                                url=article["url"],
                                description=article.get("description", ""),
                                publisher=article.get("publisher", ""),
                                published_at=article.get("published_at", ""),
                                keyword=combined,
                                portal=portal_name,
                                session_id=session_id,
                            )
                            if is_new:
                                new_count += 1
                    except Exception as e:
                        err_msg = f"[{portal_name}] AND 검색 '{combined}': {e}"
                        self.errors.append(err_msg)
                        logger.error(f"즉시수집 에러: {err_msg}")
                else:
                    for keyword in keywords:
                        try:
                            articles = crawler.search_all_pages(keyword, max_pages=3, start_date=start_date)
                            total_count += len(articles)
                            for article in articles:
                                is_new = insert_news(
                                    conn,
                                    title=article["title"],
                                    url=article["url"],
                                    description=article.get("description", ""),
                                    publisher=article.get("publisher", ""),
                                    published_at=article.get("published_at", ""),
                                    keyword=keyword,
                                    portal=portal_name,
                                    session_id=session_id,
                                )
                                if is_new:
                                    new_count += 1
                        except Exception as e:
                            err_msg = f"[{portal_name}] '{keyword}': {e}"
                            self.errors.append(err_msg)
                            logger.error(f"즉시수집 에러: {err_msg}")

            if session_id:
                complete_crawl_session(conn, session_id, new_count, total_count)
            conn.close()
            self.new_count = new_count
            self.total_count = total_count
            self.last_run = datetime.now()
            self.last_error = "; ".join(self.errors) if self.errors else None
            logger.info(f"즉시수집 완료: 총 {total_count}건 수집, 신규 {new_count}건, 에러 {len(self.errors)}건")

        except Exception as e:
            self.last_error = str(e)
            self.errors.append(str(e))
            logger.error(f"즉시수집 에러: {e}")
        finally:
            self.is_run_once = False
            if self._on_complete:
                try:
                    self._on_complete()
                except Exception:
                    pass

    def shutdown(self):
        self.stop_crawling()
        self.scheduler.shutdown(wait=False)
