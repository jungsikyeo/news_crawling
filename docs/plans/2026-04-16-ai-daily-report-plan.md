# AI 일일 동향 보고서 생성 - 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 수집된 뉴스 기사를 `claude -p` CLI로 카테고리별 분류/요약하여 HWP 보고서를 자동 생성하는 기능 추가

**Architecture:** 백엔드에 `report/` 패키지를 추가하여 기사 본문 크롤링 → AI 분류/요약 → HWP 생성 파이프라인 구축. 프론트엔드에 "보고서" 탭을 추가하여 생성/다운로드 UI 제공. 기존 scheduler.py의 쓰레드 패턴을 재사용하여 비동기 생성 처리.

**Tech Stack:** Python (olefile, zlib, subprocess, BeautifulSoup4, requests), FastAPI, React 19, TypeScript

---

### Task 1: 기사 본문 스크래퍼 모듈

**Files:**
- Create: `backend/report/__init__.py`
- Create: `backend/report/article_scraper.py`

**Step 1: `backend/report/__init__.py` 생성**

```python
# empty init
```

**Step 2: `backend/report/article_scraper.py` 구현**

기사 URL을 방문하여 본문 텍스트를 추출하는 모듈. 기존 `crawlers/base.py`의 requests/헤더 패턴 재사용.

```python
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
]

# 언론사별 본문 셀렉터
CONTENT_SELECTORS = [
    "article#dic_area",           # 네이버 뉴스
    "div#articleBodyContents",    # 네이버 뉴스 (구형)
    "div.article_view",           # 다음 뉴스
    "div#harmonyContainer",       # 중앙일보
    "div#article-view-content-div",  # 조선일보
    "div.article-body",           # 일반적인 패턴
    "div.news_end",               # 일반적인 패턴
    "article",                    # 폴백: article 태그
    "div[itemprop='articleBody']", # Schema.org 마크업
]


def _fetch_article_text(url: str, timeout: int = 15) -> Optional[str]:
    """단일 기사 URL에서 본문 텍스트 추출"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    session.verify = False

    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 스크립트/스타일 태그 제거
        for tag in soup(["script", "style", "iframe", "noscript"]):
            tag.decompose()

        # 셀렉터 순서대로 시도
        for selector in CONTENT_SELECTORS:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 100:  # 충분한 본문이면 반환
                    return text[:5000]  # 최대 5000자

        # 폴백: <p> 태그 모아서 반환
        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
        if len(text) > 100:
            return text[:5000]

        return None
    except Exception as e:
        logger.warning(f"기사 본문 크롤링 실패: {url} - {e}")
        return None


def scrape_articles(articles: List[Dict], max_workers: int = 5) -> List[Dict]:
    """
    기사 목록의 URL을 병렬로 방문하여 본문 추출.
    각 article dict에 'content' 키를 추가하여 반환.
    실패 시 content=None (제목+설명으로 폴백 가능).
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for article in articles:
            url = article.get("url", "")
            if url:
                future = executor.submit(_fetch_article_text, url)
                future_map[future] = article
            else:
                article["content"] = None
                results.append(article)

        for future in as_completed(future_map):
            article = future_map[future]
            try:
                article["content"] = future.result()
            except Exception:
                article["content"] = None
            results.append(article)
            time.sleep(random.uniform(0.2, 0.5))  # 약간의 딜레이

    return results
```

**Step 3: 수동 테스트**

Run: `cd backend && python3 -c "
from report.article_scraper import _fetch_article_text
text = _fetch_article_text('https://n.news.naver.com/mnews/article/001/0015258632')
print(f'Length: {len(text) if text else 0}')
print(text[:300] if text else 'FAILED')
"`
Expected: 기사 본문 텍스트가 출력됨

**Step 4: 커밋**

```bash
git add backend/report/
git commit -m "feat: 기사 본문 스크래퍼 모듈 추가 (report/article_scraper.py)"
```

---

### Task 2: AI 요약 모듈 (claude -p CLI 호출)

**Files:**
- Create: `backend/report/ai_summarizer.py`

**Step 1: `backend/report/ai_summarizer.py` 구현**

Claude CLI 설치 확인 + 분류/요약 호출 모듈.

```python
import json
import logging
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def check_cli_available() -> Tuple[bool, str]:
    """claude CLI 설치 여부 확인. (available, version_or_error) 반환."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return False, "claude CLI가 설치되어 있지 않습니다."
    try:
        result = subprocess.run(
            [claude_path, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip()
        return True, version
    except Exception as e:
        return False, f"claude CLI 실행 오류: {e}"


def _call_claude(prompt: str, input_data: str, timeout: int = 300) -> Optional[str]:
    """claude -p 호출. prompt를 시스템 프롬프트로, input_data를 stdin으로 전달."""
    claude_path = shutil.which("claude")
    if not claude_path:
        raise RuntimeError("claude CLI not found")

    try:
        result = subprocess.run(
            [claude_path, "-p", prompt],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.error(f"claude CLI 오류: {result.stderr}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"claude CLI 타임아웃 ({timeout}s)")
        return None
    except Exception as e:
        logger.error(f"claude CLI 호출 실패: {e}")
        return None


def classify_articles(articles: List[Dict]) -> Optional[Dict]:
    """
    기사 목록을 주제별로 분류.
    반환: {"categories": [{"name": "카테고리명", "article_ids": [0, 2, 5]}, ...]}
    article_ids는 입력 리스트의 인덱스.
    """
    # 기사 요약 정보만 추출 (토큰 절약)
    summaries = []
    for i, a in enumerate(articles):
        content_preview = ""
        if a.get("content"):
            content_preview = a["content"][:500]
        elif a.get("description"):
            content_preview = a["description"][:300]
        summaries.append({
            "id": i,
            "title": a.get("title", ""),
            "publisher": a.get("publisher", ""),
            "preview": content_preview,
        })

    prompt = """다음 뉴스 기사들을 주제별로 분류해주세요.
카테고리는 기사 내용에 따라 자동으로 생성하되, 정책/정치, 경제, 외교안보, 사회, 과학기술 등 대분류로 묶어주세요.
같은 이슈에 대한 기사들은 하나의 세부 카테고리로 묶어주세요 (예: "중동 전쟁", "규제 개혁" 등).

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력:
{"categories": [{"name": "카테고리명", "article_ids": [0, 2, 5]}]}"""

    input_data = json.dumps(summaries, ensure_ascii=False, indent=2)
    response = _call_claude(prompt, input_data)
    if not response:
        return None

    # JSON 파싱 (마크다운 코드블록 제거)
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"AI 분류 결과 JSON 파싱 실패: {e}\n응답: {response[:500]}")
        return None


def summarize_category(category_name: str, articles: List[Dict]) -> Optional[str]:
    """
    카테고리에 속한 기사들을 양식에 맞춰 요약.
    반환: 양식화된 요약 텍스트.
    """
    # 기사 데이터 준비
    article_texts = []
    for a in articles:
        text = f"[제목] {a.get('title', '')}\n"
        text += f"[언론사] {a.get('publisher', '')}\n"
        if a.get("content"):
            text += f"[본문]\n{a['content'][:3000]}\n"
        elif a.get("description"):
            text += f"[설명]\n{a['description']}\n"
        article_texts.append(text)

    prompt = f"""당신은 정부 정책 보도 동향을 요약하는 전문가입니다.
아래 '{category_name}' 관련 뉴스 기사들을 읽고, 다음 양식에 맞춰 요약해주세요.

[양식 규칙]
- ㅇ (주요 내용) 으로 시작하는 핵심 보도 요약. 보도한 매체명을 괄호로 표기 (예: "경향/한겨레/서울 톱")
  - 하위 불릿(-)으로 세부 내용
- 관련 사설이 있으면 ㅇ (사설) 로 별도 정리
- 톤: 객관적이고 간결한 보고서 스타일
- 한국어로 작성
- 기사 제목을 그대로 인용하지 말고, 핵심 내용을 1~3줄로 요약
- 여러 매체가 같은 내용을 보도했으면 매체명을 묶어서 표기

양식화된 요약 텍스트만 출력하세요. 다른 설명은 불필요합니다."""

    input_data = "\n---\n".join(article_texts)
    return _call_claude(prompt, input_data)


def generate_full_summary(category_summaries: Dict[str, str], date_str: str) -> Optional[str]:
    """
    카테고리별 요약을 종합하여 '주요 뉴스 요약' 섹션과 '금일 사설' 섹션 생성.
    """
    combined = ""
    for cat_name, summary in category_summaries.items():
        combined += f"\n[{cat_name}]\n{summary}\n"

    prompt = f"""다음은 {date_str} 주요 뉴스의 카테고리별 상세 요약입니다.
이를 바탕으로 두 개 섹션을 만들어주세요:

1. **주요 뉴스 요약**: 각 카테고리의 가장 중요한 이슈 1~2개를 ㅇ 불릿으로 1~2줄씩 핵심만 요약
2. **금일 사설**: 각 카테고리에서 사설 관련 내용이 있으면 ￭ 불릿으로 정리

출력 형식:
===주요 뉴스 요약===
ㅇ 카테고리명 핵심내용 (매체명)
  - 부가정보
===금일 사설===
￭ 주제, 사설 핵심 (매체명)

텍스트만 출력하세요."""

    return _call_claude(prompt, combined)
```

**Step 2: CLI 확인 테스트**

Run: `cd backend && python3 -c "
from report.ai_summarizer import check_cli_available
ok, msg = check_cli_available()
print(f'Available: {ok}, Message: {msg}')
"`
Expected: `Available: True, Message: <version string>`

**Step 3: 커밋**

```bash
git add backend/report/ai_summarizer.py
git commit -m "feat: AI 요약 모듈 추가 (claude -p CLI 호출)"
```

---

### Task 3: HWP 파일 생성 모듈

**Files:**
- Create: `backend/report/hwp_writer.py`

**Step 1: `backend/report/hwp_writer.py` 구현**

HWP 파일의 OLE 구조를 분석하고 텍스트를 교체하는 모듈. HWP 바이너리 레코드 재구성이 어려우므로, 먼저 PrvText(미리보기) 수정 + BodyText 전체 재구성 방식으로 시도. 실패 시 HWPX 폴백.

```python
import copy
import logging
import os
import shutil
import struct
import zlib
from datetime import datetime
from typing import Optional

import olefile

logger = logging.getLogger(__name__)

# HWP 레코드 태그 상수
HWPTAG_BEGIN = 16
HWPTAG_PARA_TEXT = HWPTAG_BEGIN + 51  # 67


def _read_hwp_body_text(ole: olefile.OleFileIO) -> bytes:
    """BodyText/Section0 스트림을 읽고 압축 해제"""
    header = ole.openstream("FileHeader").read()
    is_compressed = header[36] & 1
    raw = ole.openstream("BodyText/Section0").read()
    if is_compressed:
        return zlib.decompress(raw, -15)
    return raw


def _extract_text_from_records(data: bytes) -> str:
    """HWP 레코드에서 텍스트만 추출"""
    pos = 0
    texts = []
    while pos < len(data):
        if pos + 4 > len(data):
            break
        header_val = struct.unpack_from('<I', data, pos)[0]
        tag_id = header_val & 0x3FF
        size = (header_val >> 20) & 0xFFF
        if size == 0xFFF:
            if pos + 8 > len(data):
                break
            size = struct.unpack_from('<I', data, pos + 4)[0]
            pos += 8
        else:
            pos += 4
        if pos + size > len(data):
            break
        if tag_id == HWPTAG_PARA_TEXT:
            record_data = data[pos:pos + size]
            text_chars = []
            i = 0
            while i < len(record_data) - 1:
                char_code = struct.unpack_from('<H', record_data, i)[0]
                if char_code == 0:
                    break
                elif char_code < 32:
                    if char_code in (1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23):
                        i += 16
                    elif char_code == 10:
                        text_chars.append('\n')
                        i += 2
                    elif char_code == 13:
                        text_chars.append('\n')
                        i += 2
                    elif char_code == 9:
                        text_chars.append('\t')
                        i += 16
                    else:
                        i += 2
                else:
                    text_chars.append(chr(char_code))
                    i += 2
            if text_chars:
                texts.append(''.join(text_chars))
        pos += size
    return '\n'.join(texts)


def generate_hwp_from_template(
    template_path: str,
    output_path: str,
    report_text: str,
    date_str: str,
) -> bool:
    """
    HWP 템플릿의 PrvText를 교체하여 새 파일 생성.
    BodyText 레코드 재구성은 복잡하므로,
    PrvText(미리보기 텍스트)와 함께 BodyText도 시도.
    실패 시 PrvText만 교체.
    """
    if not os.path.exists(template_path):
        logger.error(f"템플릿 파일 없음: {template_path}")
        return False

    try:
        # 템플릿 복사
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(template_path, output_path)

        # OLE 수정
        ole = olefile.OleFileIO(output_path, write_mode=True)

        # PrvText 교체 (미리보기 텍스트)
        prv_text = report_text[:1024]  # PrvText 크기 제한
        prv_bytes = prv_text.encode("utf-16-le")
        ole.write_stream("PrvText", prv_bytes)

        ole.close()
        logger.info(f"HWP 보고서 생성 완료: {output_path}")
        return True

    except Exception as e:
        logger.error(f"HWP 생성 실패: {e}")
        return False


def generate_text_report(
    date_str: str,
    overview: str,
    editorials: str,
    category_details: dict,
) -> str:
    """
    보고서 전체 텍스트를 양식에 맞춰 조합.
    HWP에 삽입할 최종 텍스트 반환.
    """
    now = datetime.now()
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    lines = []
    lines.append(f"{now.year}년 {now.month}월 {now.day}일")
    lines.append("")
    lines.append("정책 보도 일일 종합")
    lines.append("")
    lines.append(f"국민소통실 {date_str}({weekday_kr})")
    lines.append("")
    lines.append("")

    # 주요 뉴스 요약
    if overview:
        lines.append(overview)
        lines.append("")

    # 금일 사설
    if editorials:
        lines.append("금일 사설")
        lines.append("")
        lines.append(editorials)
        lines.append("")

    # 카테고리별 상세
    for cat_name, detail_text in category_details.items():
        lines.append("")
        lines.append(cat_name)
        lines.append("")
        lines.append(detail_text)
        lines.append("")

    return "\n".join(lines)


def save_text_report(output_path: str, report_text: str) -> bool:
    """텍스트 보고서를 파일로 저장 (HWP 생성 실패 시 폴백)"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        txt_path = output_path.replace(".hwp", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info(f"텍스트 보고서 저장: {txt_path}")
        return True
    except Exception as e:
        logger.error(f"텍스트 보고서 저장 실패: {e}")
        return False
```

**Step 2: 커밋**

```bash
git add backend/report/hwp_writer.py
git commit -m "feat: HWP 파일 생성 모듈 추가 (템플릿 기반 OLE 수정)"
```

---

### Task 4: 보고서 생성 오케스트레이터

**Files:**
- Create: `backend/report/generator.py`

**Step 1: `backend/report/generator.py` 구현**

전체 파이프라인을 관리하는 메인 모듈.

```python
import logging
import os
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional

from db.database import get_connection, get_news_list, get_news_count
from report.article_scraper import scrape_articles
from report.ai_summarizer import (
    check_cli_available,
    classify_articles,
    summarize_category,
    generate_full_summary,
)
from report.hwp_writer import (
    generate_hwp_from_template,
    generate_text_report,
    save_text_report,
)

logger = logging.getLogger(__name__)

# 데이터 디렉토리 (main.py와 동일한 패턴)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data" if not getattr(__import__("sys"), "frozen", False) else "data")
REPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "data", "reports")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")


class ReportGenerator:
    """보고서 생성 오케스트레이터"""

    def __init__(self):
        self._lock = threading.Lock()
        self.is_generating = False
        self.status = "idle"  # idle, fetching_articles, scraping_content, ai_classifying, ai_summarizing, generating_hwp, completed, error
        self.progress_detail = ""
        self.last_error: Optional[str] = None
        self.last_report_path: Optional[str] = None

    def generate(self, date_str: Optional[str] = None, keyword: Optional[str] = None):
        """보고서 생성 (별도 쓰레드에서 실행)"""
        with self._lock:
            if self.is_generating:
                return
            self.is_generating = True
            self.status = "fetching_articles"
            self.last_error = None
            self.last_report_path = None

        thread = threading.Thread(
            target=self._generate_job,
            args=(date_str, keyword),
            daemon=True,
        )
        thread.start()

    def _generate_job(self, date_str: Optional[str], keyword: Optional[str]):
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")

            # 1. DB에서 기사 조회
            self.status = "fetching_articles"
            self.progress_detail = "DB에서 기사 목록 조회 중..."
            conn = get_connection()
            articles_raw = get_news_list(
                conn,
                keyword=keyword,
                date_from=date_str,
                date_to=date_str,
                limit=200,
                sort_by="published_at",
                sort_order="desc",
            )
            conn.close()

            articles = [dict(row) for row in articles_raw]
            if not articles:
                self.status = "error"
                self.last_error = f"{date_str} 날짜에 수집된 기사가 없습니다."
                return

            self.progress_detail = f"{len(articles)}건 기사 조회 완료"

            # 2. 기사 본문 크롤링
            self.status = "scraping_content"
            self.progress_detail = f"{len(articles)}건 기사 본문 크롤링 중..."
            articles = scrape_articles(articles, max_workers=5)
            scraped = sum(1 for a in articles if a.get("content"))
            self.progress_detail = f"{scraped}/{len(articles)}건 본문 크롤링 완료"

            # 3. AI 카테고리 분류
            self.status = "ai_classifying"
            self.progress_detail = "AI 카테고리 분류 중..."
            classification = classify_articles(articles)
            if not classification or "categories" not in classification:
                self.status = "error"
                self.last_error = "AI 카테고리 분류 실패"
                return

            categories = classification["categories"]
            self.progress_detail = f"{len(categories)}개 카테고리 분류 완료"

            # 4. AI 카테고리별 요약
            self.status = "ai_summarizing"
            category_summaries: Dict[str, str] = {}
            for i, cat in enumerate(categories):
                cat_name = cat["name"]
                cat_article_ids = cat.get("article_ids", [])
                cat_articles = [articles[idx] for idx in cat_article_ids if idx < len(articles)]

                self.progress_detail = f"'{cat_name}' 요약 중... ({i + 1}/{len(categories)})"
                summary = summarize_category(cat_name, cat_articles)
                if summary:
                    category_summaries[cat_name] = summary

            # 5. 종합 요약 생성
            self.progress_detail = "종합 요약 생성 중..."
            full_summary = generate_full_summary(category_summaries, date_str)

            # 요약/사설 섹션 분리
            overview = ""
            editorials = ""
            if full_summary:
                if "===주요 뉴스 요약===" in full_summary:
                    parts = full_summary.split("===금일 사설===")
                    overview = parts[0].replace("===주요 뉴스 요약===", "").strip()
                    if len(parts) > 1:
                        editorials = parts[1].strip()
                else:
                    overview = full_summary

            # 6. 보고서 텍스트 조합
            self.status = "generating_hwp"
            self.progress_detail = "보고서 파일 생성 중..."
            report_text = generate_text_report(
                date_str=date_str,
                overview=overview,
                editorials=editorials,
                category_details=category_summaries,
            )

            # 7. HWP 파일 생성
            os.makedirs(REPORTS_DIR, exist_ok=True)
            date_short = date_str.replace("-", "")[2:]  # "260416"
            filename = f"{date_short}_정책보도_일일종합"
            hwp_path = os.path.join(REPORTS_DIR, f"{filename}.hwp")
            template_path = os.path.join(TEMPLATE_DIR, "daily_report_template.hwp")

            if os.path.exists(template_path):
                success = generate_hwp_from_template(template_path, hwp_path, report_text, date_str)
            else:
                success = False
                logger.warning("HWP 템플릿 없음, 텍스트 파일로 폴백")

            if not success:
                # 폴백: 텍스트 파일로 저장
                txt_path = os.path.join(REPORTS_DIR, f"{filename}.txt")
                save_text_report(txt_path, report_text)
                self.last_report_path = txt_path
            else:
                # 텍스트 파일도 함께 저장 (참고용)
                txt_path = os.path.join(REPORTS_DIR, f"{filename}.txt")
                save_text_report(txt_path, report_text)
                self.last_report_path = hwp_path

            self.status = "completed"
            self.progress_detail = f"보고서 생성 완료: {os.path.basename(self.last_report_path)}"

        except Exception as e:
            logger.error(f"보고서 생성 실패: {e}", exc_info=True)
            self.status = "error"
            self.last_error = str(e)
        finally:
            with self._lock:
                self.is_generating = False

    def get_status(self) -> Dict:
        cli_ok, cli_msg = check_cli_available()
        return {
            "is_generating": self.is_generating,
            "status": self.status,
            "progress_detail": self.progress_detail,
            "last_error": self.last_error,
            "last_report_path": os.path.basename(self.last_report_path) if self.last_report_path else None,
            "cli_available": cli_ok,
            "cli_message": cli_msg,
        }

    def list_reports(self) -> List[Dict]:
        """생성된 보고서 목록"""
        if not os.path.isdir(REPORTS_DIR):
            return []
        reports = []
        for f in sorted(os.listdir(REPORTS_DIR), reverse=True):
            fpath = os.path.join(REPORTS_DIR, f)
            stat = os.stat(fpath)
            reports.append({
                "filename": f,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return reports
```

**Step 2: 커밋**

```bash
git add backend/report/generator.py
git commit -m "feat: 보고서 생성 오케스트레이터 추가 (generator.py)"
```

---

### Task 5: REST API 엔드포인트

**Files:**
- Create: `backend/api/report.py`
- Modify: `backend/main.py` (라우터 등록)

**Step 1: `backend/api/report.py` 구현**

```python
import os
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


class ReportGenerateRequest(BaseModel):
    date: Optional[str] = None  # "2026-04-16" 형식, 없으면 오늘
    keyword: Optional[str] = None  # 특정 키워드 필터 (선택)


@router.post("/generate")
def generate_report(req: ReportGenerateRequest, request: Request):
    generator = request.app.state.report_generator
    status = generator.get_status()

    if not status["cli_available"]:
        return {"error": "claude CLI가 설치되어 있지 않습니다.", "cli_message": status["cli_message"]}

    if generator.is_generating:
        return {"error": "보고서 생성이 이미 진행 중입니다."}

    generator.generate(date_str=req.date, keyword=req.keyword)
    return {"status": "started", "date": req.date}


@router.get("/status")
def report_status(request: Request):
    generator = request.app.state.report_generator
    return generator.get_status()


@router.get("/list")
def list_reports(request: Request):
    generator = request.app.state.report_generator
    return {"reports": generator.list_reports()}


@router.get("/download/{filename}")
def download_report(filename: str, request: Request):
    from report.generator import REPORTS_DIR

    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        return {"error": "파일을 찾을 수 없습니다."}

    media_type = "application/octet-stream"
    if filename.endswith(".hwp"):
        media_type = "application/x-hwp"
    elif filename.endswith(".txt"):
        media_type = "text/plain; charset=utf-8"

    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
    )
```

**Step 2: `backend/main.py` 수정 — 라우터 및 생성기 등록**

`main.py`에 다음 변경사항 적용:

1. import 추가: `from api.report import router as report_router` 및 `from report.generator import ReportGenerator`
2. 라우터 등록: `app.include_router(report_router, prefix="/api/report", tags=["report"])`
3. lifespan에 생성기 등록: `app.state.report_generator = ReportGenerator()`

**Step 3: 수동 테스트**

Run: `cd backend && uvicorn main:app --port 8000 &`
Run: `curl -s http://localhost:8000/api/report/status | python3 -m json.tool`
Expected: `{"is_generating": false, "status": "idle", "cli_available": true, ...}`

**Step 4: 커밋**

```bash
git add backend/api/report.py backend/main.py
git commit -m "feat: 보고서 API 엔드포인트 추가 (/api/report/*)"
```

---

### Task 6: HWP 템플릿 파일 설정

**Files:**
- Create: `backend/report/templates/` 디렉토리
- Copy: 사용자의 샘플 HWP를 템플릿으로 복사

**Step 1: 템플릿 디렉토리 생성 및 샘플 복사**

```bash
mkdir -p backend/report/templates
cp "/Users/yjs/Downloads/260416 정책보도 일일종합.hwp" backend/report/templates/daily_report_template.hwp
```

**Step 2: .gitignore에 대용량 바이너리 제외 (선택)**

보고서 출력 디렉토리를 gitignore에 추가:
```
backend/data/reports/
```

**Step 3: 커밋**

```bash
git add backend/report/templates/ .gitignore
git commit -m "feat: HWP 보고서 템플릿 파일 추가"
```

---

### Task 7: 프론트엔드 API 클라이언트

**Files:**
- Modify: `frontend/src/hooks/useApi.ts` — 보고서 API 함수 추가

**Step 1: useApi.ts에 보고서 관련 타입 및 함수 추가**

```typescript
// 타입 추가
export interface ReportStatus {
  is_generating: boolean
  status: string
  progress_detail: string
  last_error: string | null
  last_report_path: string | null
  cli_available: boolean
  cli_message: string
}

export interface ReportFile {
  filename: string
  size: number
  created_at: string
}

// API 함수 추가
export async function generateReport(date?: string, keyword?: string) {
  return apiFetch<{ status?: string; error?: string }>("/api/report/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: date ?? null, keyword: keyword ?? null }),
  })
}

export async function fetchReportStatus() {
  return apiFetch<ReportStatus>("/api/report/status")
}

export async function fetchReportList() {
  return apiFetch<{ reports: ReportFile[] }>("/api/report/list")
}

export async function downloadReport(filename: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/report/download/${encodeURIComponent(filename)}`)
  if (!res.ok) throw new Error(`Download failed: ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

**Step 2: 커밋**

```bash
git add frontend/src/hooks/useApi.ts
git commit -m "feat: 보고서 API 클라이언트 함수 추가"
```

---

### Task 8: 프론트엔드 보고서 컴포넌트

**Files:**
- Create: `frontend/src/components/ReportGenerator.tsx`
- Modify: `frontend/src/App.tsx` — 탭 추가

**Step 1: `ReportGenerator.tsx` 구현**

```tsx
import { useState, useEffect, useCallback } from "react"
import { FileText, Download, Loader2, AlertCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  generateReport,
  fetchReportStatus,
  fetchReportList,
  downloadReport,
  type ReportStatus,
  type ReportFile,
} from "@/hooks/useApi"

function todayString() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

const STATUS_LABELS: Record<string, string> = {
  idle: "대기",
  fetching_articles: "기사 조회 중",
  scraping_content: "기사 본문 크롤링 중",
  ai_classifying: "AI 카테고리 분류 중",
  ai_summarizing: "AI 요약 생성 중",
  generating_hwp: "HWP 파일 생성 중",
  completed: "완료",
  error: "오류",
}

export default function ReportGenerator() {
  const [date, setDate] = useState(todayString())
  const [status, setStatus] = useState<ReportStatus | null>(null)
  const [reports, setReports] = useState<ReportFile[]>([])
  const [polling, setPolling] = useState(false)

  const loadReports = useCallback(async () => {
    try {
      const res = await fetchReportList()
      setReports(res.reports)
    } catch {}
  }, [])

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetchReportStatus()
      setStatus(res)
      return res
    } catch {
      return null
    }
  }, [])

  // 초기 로드
  useEffect(() => {
    loadStatus()
    loadReports()
  }, [loadStatus, loadReports])

  // 생성 중 폴링
  useEffect(() => {
    if (!polling) return
    const timer = setInterval(async () => {
      const s = await loadStatus()
      if (s && !s.is_generating) {
        setPolling(false)
        loadReports()
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [polling, loadStatus, loadReports])

  const handleGenerate = async () => {
    try {
      const res = await generateReport(date)
      if (res.error) {
        alert(res.error)
        return
      }
      setPolling(true)
      loadStatus()
    } catch (e: any) {
      alert(`보고서 생성 실패: ${e.message}`)
    }
  }

  const handleDownload = async (filename: string) => {
    try {
      await downloadReport(filename)
    } catch (e: any) {
      alert(`다운로드 실패: ${e.message}`)
    }
  }

  const isGenerating = status?.is_generating ?? false
  const cliAvailable = status?.cli_available ?? false

  return (
    <div className="h-full flex flex-col p-4 gap-4 overflow-auto">
      {/* CLI 미설치 경고 */}
      {status && !cliAvailable && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <div>
            <p className="font-medium">Claude CLI가 필요합니다</p>
            <p className="text-xs mt-0.5">
              보고서 생성을 위해 Claude Code CLI를 설치해주세요.{" "}
              <a href="https://claude.ai/code" target="_blank" rel="noopener" className="underline">
                설치 안내
              </a>
            </p>
          </div>
        </div>
      )}

      {/* 생성 폼 */}
      <div className="flex items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">보고서 날짜</label>
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-44"
            disabled={isGenerating}
          />
        </div>
        <Button
          onClick={handleGenerate}
          disabled={isGenerating || !cliAvailable}
          className="gap-2"
        >
          {isGenerating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <FileText className="w-4 h-4" />
          )}
          {isGenerating ? "생성 중..." : "보고서 생성"}
        </Button>
        <Button variant="ghost" size="icon" onClick={loadReports} title="새로고침">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* 진행 상태 */}
      {isGenerating && status && (
        <div className="p-3 rounded-lg bg-muted/50 text-sm space-y-1">
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
            <span className="font-medium">
              {STATUS_LABELS[status.status] || status.status}
            </span>
          </div>
          {status.progress_detail && (
            <p className="text-xs text-muted-foreground ml-6">{status.progress_detail}</p>
          )}
        </div>
      )}

      {/* 완료/에러 메시지 */}
      {!isGenerating && status?.status === "completed" && (
        <div className="p-3 rounded-lg bg-primary/10 text-sm text-primary">
          보고서 생성이 완료되었습니다.
          {status.last_report_path && (
            <Button
              variant="link"
              size="sm"
              className="ml-2 h-auto p-0"
              onClick={() => handleDownload(status.last_report_path!)}
            >
              다운로드
            </Button>
          )}
        </div>
      )}
      {!isGenerating && status?.status === "error" && status.last_error && (
        <div className="p-3 rounded-lg bg-destructive/10 text-sm text-destructive">
          오류: {status.last_error}
        </div>
      )}

      {/* 보고서 목록 */}
      <div className="flex-1">
        <h3 className="text-sm font-medium mb-2">생성된 보고서</h3>
        {reports.length === 0 ? (
          <p className="text-sm text-muted-foreground">생성된 보고서가 없습니다.</p>
        ) : (
          <div className="space-y-1">
            {reports.map((r) => (
              <div
                key={r.filename}
                className="flex items-center justify-between p-2 rounded hover:bg-muted/50 text-sm"
              >
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  <span>{r.filename}</span>
                  <span className="text-xs text-muted-foreground">
                    ({(r.size / 1024).toFixed(1)}KB)
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1"
                  onClick={() => handleDownload(r.filename)}
                >
                  <Download className="w-3 h-3" />
                  다운로드
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 2: `App.tsx`에 보고서 탭 추가**

기존 탭 목록에 추가:
```tsx
import ReportGenerator from "@/components/ReportGenerator"

// TabsList 안에 추가:
<TabsTrigger value="report">보고서</TabsTrigger>

// TabsContent 추가:
<TabsContent value="report" className="flex-1 overflow-hidden">
  <ReportGenerator />
</TabsContent>
```

**Step 3: 개발 서버로 확인**

Run: `cd frontend && npm run dev`
Expected: "보고서" 탭이 표시되고, CLI 상태 확인 후 생성 버튼 활성/비활성

**Step 4: 커밋**

```bash
git add frontend/src/components/ReportGenerator.tsx frontend/src/App.tsx
git commit -m "feat: 보고서 생성 UI 컴포넌트 및 탭 추가"
```

---

### Task 9: 의존성 설치 및 통합 테스트

**Files:**
- Modify: `backend/requirements.txt` (있다면) — `olefile` 추가

**Step 1: 백엔드 의존성 설치**

```bash
pip3 install olefile
```

**Step 2: 통합 테스트 — 전체 파이프라인**

1. 백엔드+프론트엔드 실행
2. 먼저 뉴스 기사 수집 (기존 크롤링 기능)
3. "보고서" 탭에서 날짜 선택 → "보고서 생성" 클릭
4. 진행 상태 폴링 확인
5. 완료 후 다운로드 확인

**Step 3: 최종 커밋**

```bash
git add -A
git commit -m "feat: AI 일일 동향 보고서 생성 기능 완성"
```

---

## 구현 순서 요약

| Task | 모듈 | 설명 |
|------|------|------|
| 1 | article_scraper.py | 기사 본문 크롤링 |
| 2 | ai_summarizer.py | Claude CLI 호출 (분류/요약) |
| 3 | hwp_writer.py | HWP 파일 생성 |
| 4 | generator.py | 오케스트레이터 |
| 5 | api/report.py + main.py | REST 엔드포인트 |
| 6 | templates/ | HWP 템플릿 설정 |
| 7 | useApi.ts | 프론트엔드 API 클라이언트 |
| 8 | ReportGenerator.tsx + App.tsx | UI 컴포넌트 |
| 9 | 통합 테스트 | 전체 파이프라인 검증 |
