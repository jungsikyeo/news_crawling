import logging
from typing import List, Dict

from crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class NaverCrawler(BaseCrawler):
    portal_name = "naver"

    def search(self, keyword: str, page: int = 1, start_date: str = "") -> List[Dict]:
        start = (page - 1) * 10 + 1
        url = "https://search.naver.com/search.naver"
        params = {
            "where": "news",
            "query": keyword,
            "start": start,
            "sort": 1,
        }
        # start_date format: "YYYY.MM.DD"
        if start_date:
            params["ds"] = start_date
            params["de"] = ""  # 끝 날짜 비워두면 오늘까지

        html = self._request(url, params)
        if not html:
            return []

        soup = self._parse_html(html)
        results = []

        # 네이버 2026 구조: fender-ui 기반
        # 제목 링크는 class에 'OhDwxoWO' 포함된 a 태그
        title_links = [
            a for a in soup.select('a[class*="fender-ui"]')
            if any('OhDwxoWO' in c for c in a.get('class', []))
            and a.get('href', '').startswith('http')
            and len(a.get_text(strip=True)) > 5
        ]

        for title_tag in title_links:
            try:
                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")
                if not link or not title:
                    continue

                publisher = ""
                published_at = ""
                description = ""

                # 부모를 거슬러 올라가서 publisher/date 찾기
                container = title_tag
                for _ in range(10):
                    container = container.parent
                    if not container:
                        break
                    profile_title = container.select_one(
                        'span.sds-comps-profile-info-title-text'
                    )
                    if profile_title:
                        publisher = profile_title.get_text(strip=True)
                        subtext = container.select_one(
                            'span.sds-comps-profile-info-subtext'
                        )
                        if subtext:
                            published_at = subtext.get_text(strip=True)
                        break

                # 본문: 제목 링크 다음의 fender-ui 링크
                desc_tag = title_tag.find_next(
                    'a', class_=lambda c: c and any('VaBVLMeL' in cls for cls in c)
                )
                if desc_tag:
                    description = desc_tag.get_text(strip=True)

                results.append({
                    "title": title,
                    "url": link,
                    "description": description,
                    "publisher": publisher,
                    "published_at": published_at,
                })
            except Exception as e:
                logger.error(f"[naver] 뉴스 파싱 에러: {e}")
                continue

        return results
