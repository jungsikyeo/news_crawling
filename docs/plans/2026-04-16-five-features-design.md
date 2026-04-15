# NewsDesk 5가지 기능 개선 설계

## 1. 키워드 AND/OR 조건 선택

### 현재
- 키워드별 개별 검색 (사실상 OR). `scheduler.py`에서 `for keyword in keywords` 반복.

### 변경
- **사이드바**: AND/OR 토글 UI 추가
- **AND 모드**: 키워드를 공백으로 합쳐 하나의 검색어로 포털에 전송 (`"AI 반도체"` → 1회 검색)
- **OR 모드**: 기존과 동일하게 키워드별 개별 검색
- **scheduler.py**: `mode` 파라미터 추가. AND면 `" ".join(keywords)`로 1회 검색, OR이면 기존 반복
- **DB**: `search_history`에 `mode TEXT DEFAULT 'OR'` 컬럼 추가
- **API**: `/api/crawl/start`, `/api/crawl/run-once` 요청에 `mode` 필드 추가

### 수정 파일
- `backend/scheduler.py` — `_crawl_job()` 분기 로직
- `backend/api/crawl.py` — `mode` 파라미터 수신
- `backend/db/database.py` — `search_history` 스키마, `save_search_history()`
- `frontend/src/components/Sidebar.tsx` — AND/OR 토글 UI
- `frontend/src/hooks/useApi.ts` — `CrawlStartData`, `RunOnceData` 타입에 `mode` 추가

---

## 2. 날짜 정렬 (기준 + 방향)

### 현재
- `ORDER BY n.crawled_at DESC` 고정. 정렬 변경 불가.

### 변경
- **백엔드** `get_news_list()`에 `sort_by` (`crawled_at`|`published_at`) + `sort_order` (`asc`|`desc`) 파라미터 추가
- **API** `/api/news`에 `sort_by`, `sort_order` 쿼리 파라미터 추가
- **프론트 필터바**:
  - 정렬 기준 셀렉트: "수집일순" / "발행일순"
  - 오름차순/내림차순 토글 버튼 (▲▼ 아이콘)

### 수정 파일
- `backend/db/database.py` — `get_news_list()` 쿼리 수정
- `backend/api/news.py` — `sort_by`, `sort_order` 파라미터
- `frontend/src/components/NewsList.tsx` — 정렬 UI + state
- `frontend/src/hooks/useApi.ts` — `NewsParams`에 정렬 필드 추가

---

## 3. 기사 링크 URL 표시 + 시스템 브라우저 실행

### 현재
- 기사 제목이 `<a href target="_blank">` 링크. URL 텍스트 미표시.
- 내장 웹뷰 환경에서 `target="_blank"`가 같은 내장 브라우저에서 열려 Ctrl+F 불가.

### 변경
- **백엔드**: `POST /api/open-url` 엔드포인트 추가 → Python `webbrowser.open(url)` 호출
- **프론트**: 기사 제목 클릭 시 `<a>` 대신 이 API 호출
- **기사 카드** 메타 영역에 URL 도메인 텍스트 표시 (예: `news.naver.com/...`)

### 수정 파일
- `backend/api/news.py` — `POST /api/open-url` 엔드포인트
- `frontend/src/components/NewsList.tsx` — 클릭 핸들러 변경, URL 텍스트 표시
- `frontend/src/hooks/useApi.ts` — `openUrl()` 함수 추가

---

## 4. 히스토리 회차별 기사 조회

### 현재
- `search_history` 테이블은 검색 세션만 기록. 기사와 연결 없음.
- `news` 테이블에 크롤링 회차 정보 없음.

### DB 변경
```sql
-- 신규 테이블
CREATE TABLE IF NOT EXISTS crawl_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    new_count INTEGER DEFAULT 0,
    total_count INTEGER DEFAULT 0,
    FOREIGN KEY (history_id) REFERENCES search_history(id)
);

-- news 테이블에 컬럼 추가
ALTER TABLE news ADD COLUMN session_id INTEGER REFERENCES crawl_sessions(id);
```

### 백엔드 변경
- `scheduler.py`: `_crawl_job()` 시작 시 `crawl_sessions` 레코드 생성, `insert_news()` 호출 시 `session_id` 전달, 종료 시 카운트 업데이트
- `database.py`: `insert_news()`에 `session_id` 파라미터 추가, `crawl_sessions` CRUD 함수
- `api/history.py`:
  - `GET /api/history/{id}/sessions` — 히스토리별 회차 목록
  - `GET /api/news?session_id=N` — 회차별 기사 조회 (기존 news API에 session_id 필터 추가)

### 프론트 변경
- `History.tsx`:
  - 히스토리 항목 클릭 → 아코디언 펼침 → 회차 목록 (1회차: 신규 5건/전체 12건, 2회차: 신규 3건/전체 10건...)
  - 회차 클릭 → 기사 목록 탭 전환 + `session_id` 필터 적용
- `App.tsx`: 히스토리→기사목록 탭 전환 콜백 추가
- `useApi.ts`: 회차 조회 API 함수 추가

### 수정 파일
- `backend/db/database.py` — 스키마, insert_news, 세션 CRUD
- `backend/scheduler.py` — 세션 생성/업데이트 로직
- `backend/api/history.py` — 회차 목록 엔드포인트
- `backend/api/news.py` — session_id 필터
- `frontend/src/components/History.tsx` — 아코디언 UI
- `frontend/src/components/App.tsx` — 탭 전환 콜백
- `frontend/src/hooks/useApi.ts` — 타입, API 함수

---

## 5. 다운로드 옵션 (회차별/전체)

### 현재
- `/api/news/export`가 필터 없이 전체 기사 CSV 내보내기만 지원.

### 변경
- **백엔드** `/api/news/export`에 필터 파라미터 추가: `session_id`, `history_id`, `keyword`, `date_from`, `date_to`
- **CSV 컬럼**: 제목, 발행일(published_at), 언론사, 링크 (4개 컬럼으로 간소화)
- **히스토리 UI**:
  - 히스토리 항목에 **전체 다운로드** 버튼 → `history_id`로 해당 키워드의 모든 회차 기사 내보내기
  - 각 회차에 **회차별 다운로드** 버튼 → `session_id`로 해당 회차 기사만 내보내기
- **기존 CSV 내보내기** (기사 목록 탭)도 현재 필터 반영하도록 개선

### 수정 파일
- `backend/db/database.py` — `get_news_list()`에 `session_id`, `history_id` 필터 추가
- `backend/api/news.py` — export 엔드포인트 필터 파라미터
- `frontend/src/components/History.tsx` — 다운로드 버튼 2종
- `frontend/src/hooks/useApi.ts` — `exportCsv()` 파라미터 확장
