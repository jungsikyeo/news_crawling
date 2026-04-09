import logging
from typing import List, Dict

from crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class DaumCrawler(BaseCrawler):
    portal_name = "daum"

    def search(self, keyword: str, page: int = 1, start_date: str = "") -> List[Dict]:
        url = "https://search.daum.net/search"
        params = {
            "w": "news",
            "q": keyword,
            "p": page,
            "sort": "recency",
        }
        # start_date format: "YYYYMMDD"
        if start_date:
            sd = start_date.replace(".", "")
            params["sd"] = sd

        html = self._request(url, params)
        if not html:
            return []

        soup = self._parse_html(html)
        results = []

        # 다음 2026 구조: div.item-title > a (제목)
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

                # 카드 컨테이너: li 레벨까지 올라가야 item-writer 접근 가능
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

                    # 언론사: a.item-writer 또는 첫 번째 span.txt_info
                    writer_tag = card.select_one("a.item-writer")
                    if writer_tag:
                        publisher = writer_tag.get_text(strip=True)

                    # 시간 정보: span.gem-subinfo 또는 두 번째 span.txt_info
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
                logger.error(f"[daum] 뉴스 파싱 에러: {e}")
                continue

        return results
