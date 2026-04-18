import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

import requests
import urllib3
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# SSL 검증 비활성화 시 경고 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 본문 추출에 사용할 CSS 셀렉터 (우선순위 순)
ARTICLE_SELECTORS = [
    "article#dic_area",
    "div#articleBodyContents",
    "div.article_view",
    "div#harmonyContainer",
    "div#article-view-content-div",
    "div.article-body",
    "div.news_end",
    "article",
    "div[itemprop='articleBody']",
]

MAX_CONTENT_LENGTH = 5000


def _create_session() -> requests.Session:
    """크롤러와 동일한 패턴의 requests 세션 생성."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    session.verify = False
    return session


def _extract_text(soup: BeautifulSoup) -> str:
    """soup에서 본문 텍스트를 추출. 셀렉터 우선순위대로 시도 후 fallback."""
    # script, style, iframe, noscript 태그 제거
    for tag in soup.find_all(["script", "style", "iframe", "noscript"]):
        tag.decompose()

    # 셀렉터 우선순위대로 시도
    for selector in ARTICLE_SELECTORS:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator="\n", strip=True)
            if len(text) > 100:
                return text[:MAX_CONTENT_LENGTH]

    # Fallback: 20자 초과 <p> 태그 수집
    paragraphs = []
    for p in soup.find_all("p"):
        p_text = p.get_text(strip=True)
        if len(p_text) > 20:
            paragraphs.append(p_text)

    if paragraphs:
        return "\n".join(paragraphs)[:MAX_CONTENT_LENGTH]

    return ""


def _fetch_article_text(url: str, timeout: int = 15) -> str:
    """단일 기사 URL에서 본문 텍스트를 추출."""
    try:
        session = _create_session()
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        return _extract_text(soup)
    except requests.exceptions.Timeout:
        logger.warning(f"기사 본문 가져오기 타임아웃: {url}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"기사 본문 가져오기 실패: {url} - {e}")
    except Exception as e:
        logger.error(f"기사 본문 파싱 에러: {url} - {e}")
    return ""


def scrape_articles(articles: List[Dict], max_workers: int = 5, on_progress=None) -> List[Dict]:
    """기사 목록의 URL로부터 본문을 병렬로 가져와 'content' 키에 추가.

    Args:
        on_progress: 콜백 함수 (done_count, total_count) — 진행률 업데이트용
    """
    if not articles:
        return articles

    logger.info(f"기사 본문 스크래핑 시작: {len(articles)}건, workers={max_workers}")
    done_count = 0
    total = len(articles)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {}
        for idx, article in enumerate(articles):
            url = article.get("url") or article.get("link", "")
            if url:
                future = executor.submit(_fetch_article_text, url)
                future_to_idx[future] = idx

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                content = future.result()
                articles[idx]["content"] = content
            except Exception as e:
                logger.error(f"기사 본문 스크래핑 에러 (index={idx}): {e}")
                articles[idx]["content"] = ""

            done_count += 1
            if on_progress:
                on_progress(done_count, total)

    # URL이 없는 기사에도 빈 content 보장
    for article in articles:
        if "content" not in article:
            article["content"] = ""

    scraped = sum(1 for a in articles if a["content"])
    logger.info(f"기사 본문 스크래핑 완료: {scraped}/{len(articles)}건 성공")

    return articles
