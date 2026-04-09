import logging
from typing import List, Dict

from crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class NateCrawler(BaseCrawler):
    portal_name = "nate"

    def search(self, keyword: str, page: int = 1, start_date: str = "") -> List[Dict]:
        # 네이트 검색은 다음 검색 엔진 기반
        url = "https://search.daum.net/nate"
        params = {
            "w": "news",
            "q": keyword,
            "p": page,
            "sort": "recency",
        }
        if start_date:
            sd = start_date.replace(".", "").replace("-", "")
            if len(sd) == 8:
                sd += "000000"
            params["sd"] = sd

        html = self._request(url, params)
        if not html:
            return []

        soup = self._parse_html(html)
        results = []

        # 네이트도 다음과 동일한 구조 사용
        title_divs = soup.select("div.item-title")

        for title_div in title_divs:
            try:
                title_a = title_div.select_one("a")
                if not title_a:
                    continue

                title = title_a.get_text(strip=True)
                link = title_a.get("href", "")
                if not title or not link:
                    continue

                card = title_div
                for _ in range(5):
                    card = card.parent
                    if not card:
                        break
                    if card.name == "li":
                        break

                description = ""
                publisher = ""
                published_at = ""

                if card:
                    desc_tag = card.select_one("p.conts-desc")
                    if desc_tag:
                        description = desc_tag.get_text(strip=True)

                    writer_tag = card.select_one("a.item-writer")
                    if writer_tag:
                        publisher = writer_tag.get_text(strip=True)

                    time_tag = card.select_one("span.gem-subinfo")
                    if time_tag:
                        published_at = time_tag.get_text(strip=True)
                    else:
                        txt_infos = card.select("span.txt_info")
                        for t in txt_infos:
                            text = t.get_text(strip=True)
                            if text != publisher:
                                published_at = text
                                break

                results.append({
                    "title": title,
                    "url": link,
                    "description": description,
                    "publisher": publisher,
                    "published_at": published_at,
                })
            except Exception as e:
                logger.error(f"[nate] 뉴스 파싱 에러: {e}")
                continue

        return results
