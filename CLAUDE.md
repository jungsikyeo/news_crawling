# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**NewsDesk** — 네이버, 다음, 네이트 뉴스 포털에서 기사를 수집하는 데스크톱 애플리케이션. FastAPI 백엔드 + React 프론트엔드 구조이며, PyInstaller로 Windows exe 패키징 가능.

## 개발 명령어

```bash
# 백엔드 실행 (개발 모드)
cd backend && uvicorn main:app --reload --port 8000

# 프론트엔드 실행 (개발 모드, /api → localhost:8000 프록시 자동 설정)
cd frontend && npm run dev

# 프론트엔드 빌드
cd frontend && npm run build

# 전체 빌드 (React 빌드 → PyInstaller exe 패키징 → Electron 설치 파일)
python build.py
```

## 아키텍처

### 전체 흐름

```
[Sidebar.tsx] → POST /api/crawl/start or /run-once
                    ↓
[scheduler.py] → CrawlScheduler._crawl_job()
                    ↓
[crawlers/*.py] → 포털별 검색 결과 HTML 파싱
                    ↓
[db/database.py] → insert_news() (중복 검출 후 저장)
                    ↓
[App.tsx] ← 2초 폴링 /api/crawl/status → 완료 감지 → 뉴스 목록 새로고침
```

### 백엔드 (Python / FastAPI)

- **`main.py`** — FastAPI 앱 진입점. CORS(전체 허용), 라우터 4개 마운트(`/api` 접두사), React 정적 파일 서빙. `lifespan`에서 DB 초기화 및 스케줄러 생성
- **`scheduler.py`** — APScheduler 기반 크롤링 오케스트레이터. mutex 락으로 동시 실행 방지, 쓰레드 풀에서 크롤링 실행, 완료 콜백 지원. `start_crawling()`은 즉시 실행 + 주기적 스케줄 등록, `run_once()`는 1회성 실행
- **`db/database.py`** — SQLite(WAL 모드). 4개 테이블(`news`, `news_portals`, `search_history`, `scraps`). 핵심 로직:
  - `normalize_title()` → `find_duplicate()`: 제목 정규화(구두점 제거, 소문자화) 후 SequenceMatcher 유사도 ≥ 0.75이면 중복 판단
  - `_resolve_relative_time()`: 한국어 상대시간("5분 전", "3시간 전", "1일 전") 및 날짜 문자열("2026.04.09") → ISO datetime 파싱
  - 동일 기사가 여러 포털에 있으면 `news` 테이블에 1건만 저장하고 `news_portals`에 포털별 참조 추가
  - 통계 함수 6종: 일별, 키워드별, 포털별, 언론사별(상위 30), 수집시간대별, 발행시간대별
- **`crawlers/`** — `BaseCrawler` 추상 클래스 상속. 재시도 3회(지수 백오프), 429 레이트리밋 대응, 15초 타임아웃, User-Agent 랜덤 회전. `search_all_pages()`는 1~3페이지 순회하며 0.5~1.5초 딜레이
  - `naver.py`: `a[class*="fender-ui"]` 셀렉터. 부모 DOM 10레벨까지 탐색하여 메타데이터 추출
  - `daum.py`: `div.item-title > a` 셀렉터. li 컨테이너까지 상위 탐색
  - `nate.py`: 다음 검색엔진 공유 (`search.daum.net/nate`), daum과 동일한 DOM 파싱
- **`api/`** — REST 엔드포인트:
  - `crawl.py`: 수집 시작/중지/즉시수집/상태조회
  - `news.py`: 기사 목록(필터링+페이징)/스크랩 토글/CSV 내보내기(UTF-8-sig BOM)/데이터 초기화
  - `stats.py`: 6종 통계(날짜 범위, 키워드, 포털 필터 지원)
  - `history.py`: 검색이력 조회/삭제

### 프론트엔드 (React 19 / TypeScript / Vite)

- **`App.tsx`** — 탭 기반 레이아웃(기사목록/분석/스크랩/이력). 크롤링 활성 시 2초 간격 상태 폴링. `is_running` true→false 전환 감지로 완료 처리(뉴스 새로고침 또는 성공 모달 3초 자동닫힘)
- **`hooks/useApi.ts`** — 전체 API 클라이언트 및 타입 정의. `apiFetch<T>()` 제네릭 래퍼 기반
- **`components/Sidebar.tsx`** — 키워드 입력(뱃지 형태), 포털 체크박스(로고 이미지), 수집 간격(15분~24시간), 시작일 선택, 시작/중지/즉시수집/초기화 버튼. 키워드+포털 미선택 시 경고 모달
- **`components/NewsList.tsx`** — Intersection Observer 기반 무한 스크롤(20건 단위). 키워드/포털/날짜/텍스트 필터링. 스크랩 토글(별 아이콘)
- **`components/Analytics.tsx`** — ECharts 차트 6종. CSS 변수(`--primary`)에서 차트 테마 색상 추출. 날짜 범위 프리셋
- **`components/ThemeSelector.tsx`** — 다크 5종(Midnight/Emerald/Rose/Amber/Ocean) + 라이트 3종(Light/Paper/Arctic). `data-theme` 속성 + localStorage(`news-dashboard-theme`) 저장
- **`lib/highlight.tsx`** — 검색어 텍스트 하이라이팅 유틸
- **`components/ui/`** — Radix UI 래핑 컴포넌트(badge, button, input, tabs)

### 주의사항

- **DB 위치**: 개발 시 `backend/data/news.db`, exe 빌드 시 `NewsDesk_exe/data/`
- **포털 크롤러 DOM 구조**: 네이버는 2026년 기준 `fender-ui` 클래스 셀렉터 사용. 포털 사이트 DOM 변경 시 크롤러 업데이트 필요
- **빌드 시 hidden imports**: `build.py`에 uvicorn/APScheduler/BS4/lxml 등의 서브모듈을 명시적으로 지정해야 PyInstaller가 올바르게 패키징
- **CORS 전체 허용**: 로컬 데스크톱 앱 전용이므로 `allow_origins=["*"]` 설정. 외부 배포 시 수정 필요
- **CSV 내보내기**: 한글 엑셀 호환을 위해 UTF-8-sig(BOM) 인코딩 사용

### 기술 스택

- **백엔드**: Python, FastAPI, Uvicorn, SQLite(WAL), APScheduler, BeautifulSoup4, lxml, Requests, Pandas
- **프론트엔드**: React 19, TypeScript, Vite, Tailwind CSS v4, ECharts, Radix UI, Lucide React
- **빌드/배포**: PyInstaller (Windows exe, onedir 모드)
