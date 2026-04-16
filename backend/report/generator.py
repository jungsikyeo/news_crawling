"""보고서 생성 오케스트레이터.

기사 스크래핑, AI 분류/요약, HWP/TXT 보고서 생성을 하나의 파이프라인으로 연결한다.
scheduler.py와 동일한 패턴(threading.Lock, daemon thread, status tracking)을 사용한다.
"""

import logging
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from db.database import get_connection, get_news_list
from report.article_scraper import scrape_articles
from report.ai_summarizer import (
    check_cli_available,
    classify_articles,
    generate_full_summary,
    summarize_category,
)
from report.hwp_writer import (
    generate_hwp_from_template,
    generate_text_report,
    save_text_report,
)

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports"
)
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


class ReportGenerator:
    """보고서 생성 파이프라인 오케스트레이터."""

    def __init__(self):
        self._lock = threading.Lock()
        self.is_generating: bool = False
        self.status: str = "idle"
        self.progress_detail: str = ""
        self.last_error: Optional[str] = None
        self.last_report_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, date_str: Optional[str] = None, user_categories: Optional[List[str]] = None):
        """보고서 생성을 시작한다. 이미 실행 중이면 무시.

        Args:
            date_str: 대상 날짜 (기본: 오늘)
            user_categories: 사용자 지정 카테고리 리스트. None이면 AI 자동 분류.
        """
        if not self._lock.acquire(blocking=False):
            logger.warning("보고서 생성이 이미 진행 중입니다.")
            return

        try:
            self.is_generating = True
            self.status = "idle"
            self.progress_detail = ""
            self.last_error = None

            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")

            t = threading.Thread(
                target=self._generate_job, args=(date_str, user_categories), daemon=True
            )
            t.start()
        except Exception:
            self.is_generating = False
            self._lock.release()
            raise

    def get_status(self) -> Dict:
        """현재 생성 상태를 딕셔너리로 반환한다."""
        cli_available, cli_message = check_cli_available()
        return {
            "is_generating": self.is_generating,
            "status": self.status,
            "progress_detail": self.progress_detail,
            "last_error": self.last_error,
            "last_report_path": (
                os.path.basename(self.last_report_path)
                if self.last_report_path
                else None
            ),
            "cli_available": cli_available,
            "cli_message": cli_message,
        }

    def list_reports(self) -> List[Dict]:
        """REPORTS_DIR 내 보고서 파일 목록을 최신순으로 반환한다."""
        os.makedirs(REPORTS_DIR, exist_ok=True)
        reports: List[Dict] = []
        for fname in os.listdir(REPORTS_DIR):
            fpath = os.path.join(REPORTS_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            stat = os.stat(fpath)
            reports.append(
                {
                    "filename": fname,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                }
            )
        reports.sort(key=lambda r: r["created_at"], reverse=True)
        return reports

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _generate_job(self, date_str: str, user_categories: Optional[List[str]]):
        """메인 파이프라인. daemon thread에서 실행된다."""
        try:
            # --- Step 1: DB에서 기사 목록 가져오기 ---
            self.status = "fetching_articles"
            self.progress_detail = "DB에서 기사 목록을 가져오는 중..."
            logger.info(f"[보고서] Step 1: 기사 목록 조회 (date={date_str}, categories={user_categories})")

            conn = get_connection()
            try:
                rows = get_news_list(
                    conn,
                    date_from=date_str,
                    date_to=date_str,
                    limit=200,
                    sort_by="published_at",
                    sort_order="desc",
                )
            finally:
                conn.close()

            articles = [dict(row) for row in rows]
            if not articles:
                raise ValueError(f"{date_str} 날짜에 해당하는 기사가 없습니다.")

            self.progress_detail = f"기사 {len(articles)}건 조회 완료"
            logger.info(f"[보고서] 기사 {len(articles)}건 조회됨")

            # --- Step 2: 기사 본문 스크래핑 ---
            self.status = "scraping_content"
            self.progress_detail = f"기사 본문 스크래핑 중... (0/{len(articles)})"
            logger.info("[보고서] Step 2: 기사 본문 스크래핑")

            articles = scrape_articles(articles, max_workers=5)

            scraped_count = sum(1 for a in articles if a.get("content"))
            self.progress_detail = f"본문 스크래핑 완료 ({scraped_count}/{len(articles)}건)"
            logger.info(f"[보고서] 본문 스크래핑 완료: {scraped_count}/{len(articles)}건")

            # --- Step 3: AI 기사 분류 ---
            self.status = "ai_classifying"
            if user_categories:
                self.progress_detail = f"지정 카테고리({', '.join(user_categories)})로 분류 중..."
            else:
                self.progress_detail = "AI로 기사 자동 분류 중..."
            logger.info(f"[보고서] Step 3: AI 기사 분류 (user_categories={user_categories})")

            classification_result = classify_articles(articles, user_categories=user_categories)
            if not classification_result or "categories" not in classification_result:
                raise RuntimeError("AI 기사 분류에 실패했습니다. (classify_articles 반환값 없음)")

            # classify_articles 반환: {"categories": [{"name": "...", "article_ids": [0,2,5]}]}
            # 이를 {카테고리명: [기사dict 리스트]} 형태로 변환
            classification: Dict[str, List[Dict]] = {}
            for cat in classification_result["categories"]:
                cat_name = cat["name"]
                cat_article_ids = cat.get("article_ids", [])
                cat_articles = [articles[idx] for idx in cat_article_ids if idx < len(articles)]
                if cat_articles:
                    classification[cat_name] = cat_articles

            categories = list(classification.keys())
            self.progress_detail = f"기사 분류 완료 ({len(categories)}개 카테고리)"
            logger.info(f"[보고서] 분류 완료: {categories}")

            # --- Step 4: 카테고리별 요약 ---
            self.status = "ai_summarizing"
            category_summaries: Dict[str, str] = {}
            for i, (cat_name, cat_articles) in enumerate(classification.items(), 1):
                self.progress_detail = f"카테고리 요약 중... ({i}/{len(categories)}) - {cat_name}"
                logger.info(f"[보고서] Step 4: 카테고리 요약 - {cat_name} ({len(cat_articles)}건)")

                summary = summarize_category(cat_name, cat_articles)
                if summary:
                    category_summaries[cat_name] = summary

            if not category_summaries:
                raise RuntimeError("카테고리 요약을 하나도 생성하지 못했습니다.")

            self.progress_detail = f"카테고리 요약 완료 ({len(category_summaries)}개)"
            logger.info(f"[보고서] 카테고리 요약 완료: {len(category_summaries)}개")

            # --- Step 5: 최종 종합 요약 생성 ---
            self.progress_detail = "최종 종합 요약 생성 중..."
            logger.info("[보고서] Step 5: 최종 종합 요약 생성")

            full_summary = generate_full_summary(category_summaries, date_str)

            # 주요 뉴스 요약 / 금일 사설 분리
            overview = full_summary or ""
            editorials = ""
            if full_summary and "===주요 뉴스 요약===" in full_summary:
                parts = full_summary.split("===주요 뉴스 요약===")
                if len(parts) > 1:
                    remainder = parts[1]
                    if "===금일 사설===" in remainder:
                        sub_parts = remainder.split("===금일 사설===")
                        overview = sub_parts[0].strip()
                        editorials = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                    else:
                        overview = remainder.strip()
            elif full_summary and "===금일 사설===" in full_summary:
                parts = full_summary.split("===금일 사설===")
                overview = parts[0].strip()
                editorials = parts[1].strip() if len(parts) > 1 else ""

            # --- Step 6: 보고서 파일 생성 ---
            self.status = "generating_hwp"
            self.progress_detail = "보고서 파일 생성 중..."
            logger.info("[보고서] Step 6: 보고서 파일 생성")

            os.makedirs(REPORTS_DIR, exist_ok=True)

            # 파일명: YYMMDD_정책보도_일일종합
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_short = dt.strftime("%y%m%d")
            base_name = f"{date_short}_정책보도_일일종합"

            report_text = generate_text_report(
                date_str=date_str,
                overview=overview,
                editorials=editorials,
                category_details=category_summaries,
            )

            # HWP 생성 시도 (템플릿이 있을 경우)
            hwp_path = os.path.join(REPORTS_DIR, f"{base_name}.hwp")
            template_path = os.path.join(TEMPLATE_DIR, "daily_report_template.hwp")
            hwp_ok = False
            if os.path.exists(template_path):
                hwp_ok = generate_hwp_from_template(
                    template_path=template_path,
                    output_path=hwp_path,
                    report_text=report_text,
                    date_str=date_str,
                )

            # TXT는 항상 저장 (참조용 또는 HWP 폴백)
            txt_path = os.path.join(REPORTS_DIR, f"{base_name}.txt")
            save_text_report(output_path=txt_path, report_text=report_text)

            self.last_report_path = hwp_path if hwp_ok else txt_path
            self.status = "completed"
            self.progress_detail = f"보고서 생성 완료: {os.path.basename(self.last_report_path)}"
            logger.info(f"[보고서] 생성 완료: {self.last_report_path}")

        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            self.progress_detail = f"오류 발생: {e}"
            logger.error(f"[보고서] 생성 실패: {e}", exc_info=True)

        finally:
            self.is_generating = False
            self._lock.release()
