import logging
import time
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

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


class BaseCrawler(ABC):
    portal_name: str = ""
    max_retries: int = 3
    retry_delay: float = 2.0
    request_timeout: int = 15

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.session.verify = False

    def _request(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.request_timeout)
                resp.raise_for_status()
                return resp.text
            except requests.exceptions.Timeout:
                logger.warning(f"[{self.portal_name}] 타임아웃 (시도 {attempt}/{self.max_retries}): {url}")
            except requests.exceptions.SSLError as e:
                logger.error(f"[{self.portal_name}] SSL 에러 (시도 {attempt}/{self.max_retries}): {e}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[{self.portal_name}] 연결 실패 (시도 {attempt}/{self.max_retries}): {e}")
            except requests.exceptions.HTTPError as e:
                logger.warning(f"[{self.portal_name}] HTTP 에러 {e.response.status_code} (시도 {attempt}/{self.max_retries})")
                if e.response.status_code == 429:
                    time.sleep(self.retry_delay * attempt * 2)
                    continue
            except requests.exceptions.RequestException as e:
                logger.error(f"[{self.portal_name}] 요청 에러: {e}")
                return None

            if attempt < self.max_retries:
                delay = self.retry_delay * attempt + random.uniform(0, 1)
                time.sleep(delay)

        logger.error(f"[{self.portal_name}] 최대 재시도 초과: {url}")
        return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    def search(self, keyword: str, page: int = 1, start_date: str = "") -> List[Dict]:
        pass

    def search_all_pages(self, keyword: str, max_pages: int = 3, start_date: str = "") -> List[Dict]:
        all_results = []
        for page in range(1, max_pages + 1):
            try:
                results = self.search(keyword, page, start_date=start_date)
                if not results:
                    break
                all_results.extend(results)
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                logger.error(f"[{self.portal_name}] 페이지 {page} 크롤링 실패: {e}")
                break
        return all_results
