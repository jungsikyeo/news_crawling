# NewsDesk 5가지 기능 개선 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 키워드 AND/OR 조건, 날짜 정렬, 시스템 브라우저 링크, 히스토리 회차별 조회, 회차별/전체 다운로드 5가지 기능 추가

**Architecture:** DB 스키마 확장(crawl_sessions 테이블 신규, news에 session_id 컬럼, search_history에 mode 컬럼) → 백엔드 API 확장 → 프론트엔드 UI 추가. 기존 코드 구조를 유지하면서 확장.

**Tech Stack:** Python/FastAPI/SQLite, React 19/TypeScript/Vite, Tailwind CSS, Lucide React icons

---

## Task 1: DB 스키마 확장 (crawl_sessions + news.session_id + search_history.mode)

**Files:**
- Modify: `backend/db/database.py:24-72` (init_db 함수)

**Step 1: `init_db()`에 새 테이블과 컬럼 추가**

`backend/db/database.py`의 `init_db()` 함수 내 `cursor.executescript(...)` 블록 끝에 추가:

```python
        CREATE TABLE IF NOT EXISTS crawl_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            history_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            new_count INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 0,
            FOREIGN KEY (history_id) REFERENCES search_history(id)
        );

        CREATE INDEX IF NOT EXISTS idx_crawl_sessions_history ON crawl_sessions(history_id);
        CREATE INDEX IF NOT EXISTS idx_news_session ON news(session_id);
```

그리고 `init_db()` 함수 내에서 `executescript` 후에 안전한 ALTER TABLE 추가 (이미 존재하면 무시):

```python
    # 기존 테이블에 새 컬럼 추가 (이미 존재하면 무시)
    for stmt in [
        "ALTER TABLE news ADD COLUMN session_id INTEGER REFERENCES crawl_sessions(id)",
        "ALTER TABLE search_history ADD COLUMN mode TEXT DEFAULT 'OR'",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # 이미 컬럼이 존재하면 무시
    conn.commit()
```

**Step 2: 실행 확인**

Run: `cd /Users/yjs/IdeaProjects/news_crawling/backend && python -c "from db.database import init_db; init_db(); print('OK')"`
Expected: `OK` (에러 없이 출력)

**Step 3: 커밋**

```bash
git add backend/db/database.py
git commit -m "feat: DB 스키마 확장 - crawl_sessions 테이블, news.session_id, search_history.mode 컬럼 추가"
```

---

## Task 2: crawl_sessions CRUD 함수 추가

**Files:**
- Modify: `backend/db/database.py` (파일 끝에 함수 추가)

**Step 1: 세션 CRUD 함수 추가**

`backend/db/database.py` 파일 끝에 다음 함수들 추가:

```python
def create_crawl_session(conn: sqlite3.Connection, history_id: int) -> int:
    cursor = conn.execute(
        "INSERT INTO crawl_sessions (history_id, started_at) VALUES (?, ?)",
        (history_id, datetime.now().isoformat())
    )
    conn.commit()
    return cursor.lastrowid


def complete_crawl_session(conn: sqlite3.Connection, session_id: int,
                           new_count: int, total_count: int):
    conn.execute(
        "UPDATE crawl_sessions SET completed_at = ?, new_count = ?, total_count = ? WHERE id = ?",
        (datetime.now().isoformat(), new_count, total_count, session_id)
    )
    conn.commit()


def get_sessions_by_history(conn: sqlite3.Connection, history_id: int):
    return conn.execute(
        """SELECT cs.*, 
           (SELECT COUNT(*) FROM news n WHERE n.session_id = cs.id) as article_count
           FROM crawl_sessions cs
           WHERE cs.history_id = ?
           ORDER BY cs.started_at DESC""",
        (history_id,)
    ).fetchall()
```

**Step 2: 실행 확인**

Run: `cd /Users/yjs/IdeaProjects/news_crawling/backend && python -c "from db.database import create_crawl_session, complete_crawl_session, get_sessions_by_history; print('imports OK')"`
Expected: `imports OK`

**Step 3: 커밋**

```bash
git add backend/db/database.py
git commit -m "feat: crawl_sessions CRUD 함수 추가"
```

---

## Task 3: insert_news()에 session_id 파라미터 추가

**Files:**
- Modify: `backend/db/database.py:117-151` (insert_news 함수)

**Step 1: insert_news 시그니처와 INSERT 쿼리 수정**

`insert_news()` 함수 시그니처에 `session_id: Optional[int] = None` 추가:

```python
def insert_news(conn: sqlite3.Connection, title: str, url: str, description: str,
                publisher: str, published_at: str, keyword: str, portal: str,
                session_id: Optional[int] = None) -> bool:
```

INSERT 쿼리 수정 (기존 139-145행):

```python
    cursor = conn.execute(
        """INSERT INTO news (title, url, description, publisher, published_at,
           keyword, portal, crawled_at, title_normalized, session_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, url, description, publisher, published_at, keyword, portal, now, norm, session_id)
    )
```

**Step 2: 실행 확인**

Run: `cd /Users/yjs/IdeaProjects/news_crawling/backend && python -c "from db.database import insert_news; print('OK')"`
Expected: `OK`

**Step 3: 커밋**

```bash
git add backend/db/database.py
git commit -m "feat: insert_news()에 session_id 파라미터 추가"
```

---

## Task 4: save_search_history()에 mode 파라미터 추가 + history_id 반환

**Files:**
- Modify: `backend/db/database.py:231-237` (save_search_history 함수)

**Step 1: 함수 수정**

```python
def save_search_history(conn: sqlite3.Connection, keywords: str, portals: str,
                        interval_minutes: int, mode: str = "OR") -> int:
    cursor = conn.execute(
        "INSERT INTO search_history (keywords, portals, interval_minutes, created_at, mode) VALUES (?, ?, ?, ?, ?)",
        (keywords, portals, interval_minutes, datetime.now().isoformat(), mode)
    )
    conn.commit()
    return cursor.lastrowid
```

**Step 2: 커밋**

```bash
git add backend/db/database.py
git commit -m "feat: save_search_history()에 mode 파라미터 추가, history_id 반환"
```

---

## Task 5: get_news_list()에 정렬 + session_id/history_id 필터 추가

**Files:**
- Modify: `backend/db/database.py:154-183` (get_news_list 함수)

**Step 1: 함수 시그니처 및 쿼리 수정**

```python
def get_news_list(conn: sqlite3.Connection, keyword: Optional[str] = None,
                  portal: Optional[str] = None, limit: int = 100, offset: int = 0,
                  search: Optional[str] = None,
                  date_from: Optional[str] = None, date_to: Optional[str] = None,
                  sort_by: str = "crawled_at", sort_order: str = "desc",
                  session_id: Optional[int] = None, history_id: Optional[int] = None):
    # sort_by 화이트리스트 검증
    if sort_by not in ("crawled_at", "published_at"):
        sort_by = "crawled_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    query = """
        SELECT n.*, GROUP_CONCAT(DISTINCT np.portal) as portals,
               GROUP_CONCAT(DISTINCT np.url) as portal_urls
        FROM news n
        LEFT JOIN news_portals np ON n.id = np.news_id
        WHERE 1=1
    """
    params = []
    if keyword:
        query += " AND n.keyword = ?"
        params.append(keyword)
    if portal:
        query += " AND EXISTS (SELECT 1 FROM news_portals np2 WHERE np2.news_id = n.id AND np2.portal = ?)"
        params.append(portal)
    if search:
        query += " AND (n.title LIKE ? OR n.description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if date_from:
        query += " AND DATE(n.crawled_at) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND DATE(n.crawled_at) <= ?"
        params.append(date_to)
    if session_id:
        query += " AND n.session_id = ?"
        params.append(session_id)
    if history_id:
        query += " AND n.session_id IN (SELECT id FROM crawl_sessions WHERE history_id = ?)"
        params.append(history_id)
    query += f" GROUP BY n.id ORDER BY n.{sort_by} {sort_order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return conn.execute(query, params).fetchall()
```

**Step 2: 커밋**

```bash
git add backend/db/database.py
git commit -m "feat: get_news_list()에 정렬, session_id, history_id 필터 추가"
```

---

## Task 6: scheduler.py — AND/OR 모드 + 세션 추적

**Files:**
- Modify: `backend/scheduler.py` (전체 파일)

**Step 1: import 추가 및 _crawl_job 수정**

`backend/scheduler.py` 상단 import 수정:

```python
from db.database import get_connection, insert_news, save_search_history, create_crawl_session, complete_crawl_session
```

`_crawl_job` 시그니처에 `mode`, `history_id` 추가:

```python
def _crawl_job(self, keywords: List[str], portals: List[str], start_date: str = "",
               mode: str = "OR", history_id: int = 0):
```

`_crawl_job` 내부 try 블록 수정 (기존 46-82행 전체 교체):

```python
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
                    # AND: 키워드를 공백으로 합쳐 1회 검색
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
                        logger.error(f"[{portal_name}] AND 검색 '{combined}' 에러: {e}")
                else:
                    # OR: 키워드별 개별 검색 (기존 동작)
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
                            logger.error(f"[{portal_name}] 키워드 '{keyword}' 크롤링 에러: {e}")

            if session_id:
                complete_crawl_session(conn, session_id, new_count, total_count)
            conn.close()
            self.new_count = new_count
            self.total_count = total_count
            self.last_run = datetime.now()
            self.last_error = None
            logger.info(f"크롤링 완료: 총 {total_count}건 수집, 신규 {new_count}건")
```

**Step 2: start_crawling, run_once에 mode, history_id 파라미터 추가**

```python
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

def run_once(self, keywords: List[str], portals: List[str], start_date: str = "",
             mode: str = "OR", history_id: int = 0):
    thread = threading.Thread(
        target=self._crawl_job, args=(keywords, portals, start_date, mode, history_id), daemon=True
    )
    thread.start()
```

**Step 3: 실행 확인**

Run: `cd /Users/yjs/IdeaProjects/news_crawling/backend && python -c "from scheduler import CrawlScheduler; print('OK')"`
Expected: `OK`

**Step 4: 커밋**

```bash
git add backend/scheduler.py
git commit -m "feat: scheduler에 AND/OR 모드 분기 + crawl_session 추적 추가"
```

---

## Task 7: 백엔드 API 확장 — crawl.py (mode 파라미터 + history_id 전달)

**Files:**
- Modify: `backend/api/crawl.py`

**Step 1: Request 모델에 mode 추가**

`CrawlStartRequest`에 `mode` 필드 추가:

```python
class CrawlStartRequest(BaseModel):
    keywords: List[str]
    portals: List[str]
    interval_minutes: int
    start_date: Optional[str] = ""
    mode: Optional[str] = "OR"
```

`CrawlRunOnceRequest`에도 동일:

```python
class CrawlRunOnceRequest(BaseModel):
    keywords: List[str]
    portals: List[str]
    start_date: Optional[str] = ""
    mode: Optional[str] = "OR"
```

**Step 2: start_crawl 핸들러 수정**

```python
@router.post("/start")
def start_crawl(req: CrawlStartRequest, request: Request):
    scheduler = request.app.state.scheduler
    conn = get_connection()
    history_id = save_search_history(conn, ",".join(req.keywords), ",".join(req.portals),
                                     req.interval_minutes, req.mode or "OR")
    conn.close()
    scheduler.start_crawling(req.keywords, req.portals, req.interval_minutes,
                             start_date=req.start_date or "",
                             mode=req.mode or "OR", history_id=history_id)
    return {"status": "started", "keywords": req.keywords, "portals": req.portals}
```

**Step 3: run_once 핸들러 수정**

```python
@router.post("/run-once")
def run_once(req: CrawlRunOnceRequest, request: Request):
    scheduler = request.app.state.scheduler
    conn = get_connection()
    history_id = save_search_history(conn, ",".join(req.keywords), ",".join(req.portals),
                                     0, req.mode or "OR")
    conn.close()
    scheduler.run_once(req.keywords, req.portals, start_date=req.start_date or "",
                       mode=req.mode or "OR", history_id=history_id)
    return {"status": "running"}
```

**Step 4: 커밋**

```bash
git add backend/api/crawl.py
git commit -m "feat: crawl API에 mode 파라미터 추가, history_id 전달"
```

---

## Task 8: 백엔드 API 확장 — news.py (정렬 + 필터 + open-url + export 개선)

**Files:**
- Modify: `backend/api/news.py`

**Step 1: list_news에 정렬, session_id, history_id 파라미터 추가**

```python
@router.get("")
def list_news(keyword: Optional[str] = None, portal: Optional[str] = None,
              limit: int = 50, offset: int = 0,
              search: Optional[str] = None,
              date_from: Optional[str] = None, date_to: Optional[str] = None,
              sort_by: Optional[str] = "crawled_at", sort_order: Optional[str] = "desc",
              session_id: Optional[int] = None, history_id: Optional[int] = None):
    conn = get_connection()
    items = get_news_list(conn, keyword=keyword, portal=portal, limit=limit, offset=offset,
                          search=search, date_from=date_from, date_to=date_to,
                          sort_by=sort_by or "crawled_at", sort_order=sort_order or "desc",
                          session_id=session_id, history_id=history_id)
    total = get_news_count(conn)
    conn.close()
    return {
        "total": total,
        "items": [dict(row) for row in items],
    }
```

**Step 2: open-url 엔드포인트 추가**

파일 상단에 import 추가:

```python
import webbrowser
from pydantic import BaseModel
```

핸들러 추가:

```python
class OpenUrlRequest(BaseModel):
    url: str

@router.post("/open-url")
def open_url(req: OpenUrlRequest):
    webbrowser.open(req.url)
    return {"status": "opened"}
```

**Step 3: export_csv에 필터 파라미터 추가**

```python
@router.get("/export")
def export_csv(keyword: Optional[str] = None, session_id: Optional[int] = None,
               history_id: Optional[int] = None,
               date_from: Optional[str] = None, date_to: Optional[str] = None):
    conn = get_connection()
    items = get_news_list(conn, keyword=keyword, limit=50000,
                          session_id=session_id, history_id=history_id,
                          date_from=date_from, date_to=date_to)
    conn.close()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "title", "published_at", "publisher", "url",
    ])
    writer.writeheader()
    for item in items:
        row = dict(item)
        writer.writerow({
            "title": row.get("title", ""),
            "published_at": row.get("published_at", ""),
            "publisher": row.get("publisher", ""),
            "url": row.get("url", ""),
        })

    output.seek(0)
    filename = f"newsdesk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

**Step 4: 커밋**

```bash
git add backend/api/news.py
git commit -m "feat: news API에 정렬/필터/open-url/export 필터 추가"
```

---

## Task 9: 백엔드 API 확장 — history.py (회차 목록 엔드포인트)

**Files:**
- Modify: `backend/api/history.py`

**Step 1: import 추가 및 엔드포인트 추가**

```python
from fastapi import APIRouter

from db.database import get_connection, get_search_history, delete_search_history, get_sessions_by_history

router = APIRouter()


@router.get("")
def list_history():
    conn = get_connection()
    rows = get_search_history(conn)
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{history_id}/sessions")
def list_sessions(history_id: int):
    conn = get_connection()
    sessions = get_sessions_by_history(conn, history_id)
    conn.close()
    return [dict(r) for r in sessions]


@router.delete("/{history_id}")
def remove_history(history_id: int):
    conn = get_connection()
    delete_search_history(conn, history_id)
    conn.close()
    return {"status": "deleted"}
```

**Step 2: 서버 실행 확인**

Run: `cd /Users/yjs/IdeaProjects/news_crawling/backend && python -c "from api.history import router; print('OK')"`
Expected: `OK`

**Step 3: 커밋**

```bash
git add backend/api/history.py
git commit -m "feat: 히스토리 회차 목록 조회 API 추가"
```

---

## Task 10: 프론트엔드 — useApi.ts 확장

**Files:**
- Modify: `frontend/src/hooks/useApi.ts`

**Step 1: 타입 및 API 함수 추가/수정**

`NewsParams` 인터페이스에 정렬 + 필터 필드 추가:

```typescript
export interface NewsParams {
  keyword?: string
  portal?: string
  search?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
  sort_by?: string
  sort_order?: string
  session_id?: number
  history_id?: number
}
```

`CrawlStartData`, `RunOnceData`에 mode 추가:

```typescript
export interface CrawlStartData {
  keywords: string[]
  portals: string[]
  interval: number
  search_from?: string
  mode?: string
}

export interface RunOnceData {
  keywords: string[]
  portals: string[]
  search_from?: string
  mode?: string
}
```

`fetchNews`에 새 파라미터 반영:

```typescript
export async function fetchNews(params: NewsParams = {}) {
  const query = new URLSearchParams()
  if (params.keyword) query.set("keyword", params.keyword)
  if (params.portal) query.set("portal", params.portal)
  if (params.search) query.set("search", params.search)
  if (params.date_from) query.set("date_from", params.date_from)
  if (params.date_to) query.set("date_to", params.date_to)
  if (params.limit != null) query.set("limit", String(params.limit))
  if (params.offset != null) query.set("offset", String(params.offset))
  if (params.sort_by) query.set("sort_by", params.sort_by)
  if (params.sort_order) query.set("sort_order", params.sort_order)
  if (params.session_id != null) query.set("session_id", String(params.session_id))
  if (params.history_id != null) query.set("history_id", String(params.history_id))
  const qs = query.toString()
  return apiFetch<unknown>(`/api/news${qs ? `?${qs}` : ""}`)
}
```

`startCrawl`, `runOnce`에 mode 전달:

```typescript
export async function startCrawl(data: CrawlStartData) {
  return apiFetch<unknown>("/api/crawl/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      keywords: data.keywords,
      portals: data.portals,
      interval_minutes: data.interval,
      start_date: data.search_from ?? "",
      mode: data.mode ?? "OR",
    }),
  })
}

export async function runOnce(data: RunOnceData) {
  return apiFetch<unknown>("/api/crawl/run-once", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      keywords: data.keywords,
      portals: data.portals,
      start_date: data.search_from ?? "",
      mode: data.mode ?? "OR",
    }),
  })
}
```

새 함수들 추가:

```typescript
export async function openUrl(url: string) {
  return apiFetch<unknown>("/api/news/open-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
}

export async function fetchSessions(historyId: number) {
  return apiFetch<unknown>(`/api/history/${historyId}/sessions`)
}

export interface ExportParams {
  session_id?: number
  history_id?: number
  keyword?: string
  date_from?: string
  date_to?: string
}

export async function exportCsv(params: ExportParams = {}): Promise<void> {
  const query = new URLSearchParams()
  if (params.session_id != null) query.set("session_id", String(params.session_id))
  if (params.history_id != null) query.set("history_id", String(params.history_id))
  if (params.keyword) query.set("keyword", params.keyword)
  if (params.date_from) query.set("date_from", params.date_from)
  if (params.date_to) query.set("date_to", params.date_to)
  const qs = query.toString()
  const res = await fetch(`${BASE_URL}/api/news/export${qs ? `?${qs}` : ""}`)
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `news_export_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

**Step 2: 커밋**

```bash
git add frontend/src/hooks/useApi.ts
git commit -m "feat: useApi에 정렬/세션/open-url/export 필터 API 함수 추가"
```

---

## Task 11: 프론트엔드 — Sidebar.tsx에 AND/OR 토글 추가

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

**Step 1: state 추가 및 props 확장**

`Sidebar` 컴포넌트 내에 state 추가:

```typescript
const [mode, setMode] = useState<"AND" | "OR">("OR")
```

`SidebarProps` 인터페이스의 `onStartCrawl`, `onRunOnce` 콜백에 `mode` 추가:

```typescript
interface SidebarProps {
  status: SidebarStatus
  onStartCrawl: (data: {
    keywords: string[]
    portals: string[]
    interval: number
    search_from: string
    mode: string
  }) => void
  onStopCrawl: () => void
  onRunOnce: (data: {
    keywords: string[]
    portals: string[]
    search_from: string
    mode: string
  }) => void
  onWarning?: (message: string) => void
  onReset?: () => void
}
```

`handleStart`, `handleRunOnce`에 mode 전달:

```typescript
function handleStart() {
  if (!validate()) return
  onStartCrawl({ keywords, portals, interval, search_from: searchFrom, mode })
}

function handleRunOnce() {
  if (!validate()) return
  onRunOnce({ keywords, portals, search_from: searchFrom, mode })
}
```

**Step 2: 키워드 섹션 아래에 AND/OR 토글 UI 추가**

키워드 섹션(`</section>`) 바로 뒤에 추가:

```tsx
{/* Keyword Mode */}
<section>
  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
    키워드 조건
  </p>
  <div className="flex gap-1.5">
    <button
      onClick={() => setMode("AND")}
      className={[
        "flex-1 h-7 rounded-md text-xs font-medium transition-all",
        mode === "AND"
          ? "bg-primary text-primary-foreground shadow-sm"
          : "bg-secondary text-muted-foreground hover:text-foreground",
      ].join(" ")}
    >
      AND (모두 포함)
    </button>
    <button
      onClick={() => setMode("OR")}
      className={[
        "flex-1 h-7 rounded-md text-xs font-medium transition-all",
        mode === "OR"
          ? "bg-primary text-primary-foreground shadow-sm"
          : "bg-secondary text-muted-foreground hover:text-foreground",
      ].join(" ")}
    >
      OR (각각 검색)
    </button>
  </div>
</section>
```

**Step 3: 커밋**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat: 사이드바에 AND/OR 키워드 조건 토글 추가"
```

---

## Task 12: 프론트엔드 — App.tsx에 mode 전달 + 히스토리→기사목록 탭 전환

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: handleStartCrawl, handleRunOnce에 mode 추가**

```typescript
async function handleStartCrawl(data: {
  keywords: string[]
  portals: string[]
  interval: number
  search_from: string
  mode: string
}) {
  try {
    await startCrawl({ ...data })
    showModal("success", "크롤링 시작", `${data.keywords.join(", ")} 키워드로 ${data.interval}분 간격 수집을 시작합니다.`)
    setPolling(true)
    await pollStatus()
  } catch (e) {
    showModal("error", "시작 실패", e instanceof Error ? e.message : "크롤링 시작에 실패했습니다.")
  }
}

async function handleRunOnce(data: {
  keywords: string[]
  portals: string[]
  search_from: string
  mode: string
}) {
  try {
    await runOnce({ ...data })
    runOnceWaiting.current = true
    showModal("info", "즉시 수집", "수집을 시작했습니다. 완료되면 알려드립니다.")
    setPolling(true)
    await pollStatus()
  } catch (e) {
    showModal("error", "즉시 수집 실패", e instanceof Error ? e.message : "즉시 수집에 실패했습니다.")
  }
}
```

**Step 2: 세션 필터 state + History 콜백 추가**

App 컴포넌트 상단에 state 추가:

```typescript
const [sessionFilter, setSessionFilter] = useState<number | undefined>(undefined)
```

히스토리에서 세션 선택 시 기사 목록으로 전환하는 콜백:

```typescript
function handleViewSession(sessionId: number) {
  setSessionFilter(sessionId)
  setActiveTab("articles")
}
```

**Step 3: History 컴포넌트에 콜백 전달, NewsList에 sessionFilter 전달**

```tsx
<TabsContent value="articles" className="animate-fade-up">
  <NewsList refreshRef={newsRefresh} sessionId={sessionFilter} onClearSessionFilter={() => setSessionFilter(undefined)} />
</TabsContent>

<TabsContent value="history" className="animate-fade-up">
  <History onViewSession={handleViewSession} />
</TabsContent>
```

**Step 4: 커밋**

```bash
git add frontend/src/App.tsx
git commit -m "feat: App에 mode 전달 + 히스토리→기사목록 세션필터 연결"
```

---

## Task 13: 프론트엔드 — NewsList.tsx에 정렬 UI + session 필터 + URL 표시 + 시스템 브라우저

**Files:**
- Modify: `frontend/src/components/NewsList.tsx`

**Step 1: import 추가 및 props 확장**

import에 추가:

```typescript
import { ExternalLink, Newspaper, Search, Star, ArrowUpDown, Link as LinkIcon } from "lucide-react"
import { fetchNews, toggleScrap, fetchScrapIds, openUrl } from "@/hooks/useApi"
```

props 확장:

```typescript
export function NewsList({ refreshRef, sessionId, onClearSessionFilter }: {
  refreshRef?: MutableRefObject<(() => void) | null>
  sessionId?: number
  onClearSessionFilter?: () => void
}) {
```

**Step 2: 정렬 state 추가**

기존 state 블록에 추가:

```typescript
const [sortBy, setSortBy] = useState("crawled_at")
const [sortOrder, setSortOrder] = useState("desc")
```

**Step 3: loadArticles에 정렬 + sessionId 반영**

```typescript
const loadArticles = useCallback(async (reset: boolean) => {
  if (loadingRef.current) return
  loadingRef.current = true
  setLoading(true)
  setError(null)
  try {
    const offset = reset ? 0 : offsetRef.current
    const data = await fetchNews({
      keyword: keyword || undefined,
      portal: portal || undefined,
      search: searchText || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      session_id: sessionId,
      limit: PAGE_SIZE,
      offset,
    })
    const result = data as { items?: NewsArticle[] }
    const items = result.items ?? []
    if (reset) {
      setArticles(items)
      offsetRef.current = items.length
    } else {
      setArticles((prev) => [...prev, ...items])
      offsetRef.current += items.length
    }
    setHasMore(items.length >= PAGE_SIZE)
  } catch (e) {
    setError(e instanceof Error ? e.message : "오류 발생")
  } finally {
    loadingRef.current = false
    setLoading(false)
  }
}, [keyword, portal, searchText, dateFrom, dateTo, sortBy, sortOrder, sessionId])
```

useEffect deps도 업데이트:

```typescript
useEffect(() => {
  offsetRef.current = 0
  setArticles([])
  setHasMore(true)
  loadArticles(true)
}, [keyword, portal, searchText, dateFrom, dateTo, sortBy, sortOrder, sessionId])
```

**Step 4: 필터바에 정렬 UI 추가 + 세션 필터 표시**

필터바(`<div className="flex flex-wrap gap-2 mb-4 ...">`) 안에 종료일 Input 뒤에 추가:

```tsx
<select
  value={sortBy}
  onChange={(e) => setSortBy(e.target.value)}
  className="h-8 rounded-md border border-border bg-secondary px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
>
  <option value="crawled_at">수집일순</option>
  <option value="published_at">발행일순</option>
</select>
<button
  onClick={() => setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
  className="h-8 w-8 rounded-md border border-border bg-secondary flex items-center justify-center text-foreground hover:bg-accent transition-colors"
  title={sortOrder === "desc" ? "내림차순" : "오름차순"}
>
  <ArrowUpDown className="h-3.5 w-3.5" />
</button>
```

필터바 바로 아래에 세션 필터 표시 배지 추가:

```tsx
{sessionId && (
  <div className="flex items-center gap-2 mb-2">
    <Badge className="text-xs bg-primary/10 text-primary border border-primary/20">
      회차 #{sessionId} 기사 보기
    </Badge>
    <button
      onClick={onClearSessionFilter}
      className="text-xs text-muted-foreground hover:text-foreground"
    >
      필터 해제
    </button>
  </div>
)}
```

**Step 5: 기사 제목 클릭 → 시스템 브라우저 + URL 텍스트 표시**

기존 `<a>` 태그 (257-270행)를 버튼으로 교체:

```tsx
{/* Title */}
<button
  onClick={() => openUrl(article.url)}
  className="group flex items-start gap-1 text-sm font-medium text-foreground hover:text-primary transition-colors mb-1 text-left"
>
  <span>
    {highlightText(article.title, [
      { term: article.keyword ?? "", styleKey: "keyword" },
      { term: searchText, styleKey: "search" },
    ])}
  </span>
  <ExternalLink className="h-3 w-3 flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
</button>
```

메타 영역 (286-289행)에 URL 추가:

```tsx
{/* Meta */}
<div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
  {article.publisher && <span>{article.publisher}</span>}
  {article.published_at && <span>{article.published_at}</span>}
  <span className="flex items-center gap-0.5 truncate max-w-[200px]" title={article.url}>
    <LinkIcon className="h-2.5 w-2.5 flex-shrink-0" />
    {(() => { try { return new URL(article.url).hostname } catch { return article.url } })()}
  </span>
</div>
```

**Step 6: 커밋**

```bash
git add frontend/src/components/NewsList.tsx
git commit -m "feat: 기사목록에 정렬UI, 세션필터, URL표시, 시스템브라우저 실행 추가"
```

---

## Task 14: 프론트엔드 — History.tsx 리팩터 (아코디언 + 회차 조회 + 다운로드)

**Files:**
- Modify: `frontend/src/components/History.tsx`

**Step 1: 전체 파일 교체**

```tsx
import { useState, useEffect } from "react"
import { Trash2, History as HistoryIcon, ChevronDown, ChevronRight, Download, Eye } from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchHistory, deleteHistory, fetchSessions, exportCsv } from "@/hooks/useApi"
import naverImg from "@/assets/naver.jpg"
import daumImg from "@/assets/daum.jpeg"
import nateImg from "@/assets/nate.png"

const PORTAL_IMGS: Record<string, string> = {
  naver: naverImg,
  daum: daumImg,
  nate: nateImg,
}

const PORTAL_LABELS: Record<string, string> = {
  naver: "네이버",
  daum: "다음",
  nate: "네이트",
}

interface HistoryItem {
  id: number
  keywords: string[] | string
  portals: string[] | string
  interval?: number
  interval_minutes?: number
  mode?: string
  created_at?: string
}

interface SessionItem {
  id: number
  history_id: number
  started_at: string
  completed_at?: string
  new_count: number
  total_count: number
  article_count: number
}

export function History({ onViewSession }: { onViewSession?: (sessionId: number) => void }) {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [sessions, setSessions] = useState<Record<number, SessionItem[]>>({})
  const [loadingSessions, setLoadingSessions] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchHistory()
      const raw = (data as { data?: HistoryItem[]; items?: HistoryItem[] }).data
        ?? (data as { items?: HistoryItem[] }).items
        ?? (data as HistoryItem[])
      setItems(Array.isArray(raw) ? raw : [])
    } catch (e) {
      setError(e instanceof Error ? e.message : "히스토리 로드 실패")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function toggleExpand(historyId: number) {
    if (expandedId === historyId) {
      setExpandedId(null)
      return
    }
    setExpandedId(historyId)
    if (!sessions[historyId]) {
      setLoadingSessions(historyId)
      try {
        const data = await fetchSessions(historyId)
        const list = Array.isArray(data) ? data : []
        setSessions((prev) => ({ ...prev, [historyId]: list as SessionItem[] }))
      } catch {
        setSessions((prev) => ({ ...prev, [historyId]: [] }))
      } finally {
        setLoadingSessions(null)
      }
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteHistory(id)
      setItems((prev) => prev.filter((i) => i.id !== id))
    } catch (e) {
      alert(e instanceof Error ? e.message : "삭제 실패")
    }
  }

  function formatKeywords(val: string[] | string | undefined): string {
    if (!val) return "-"
    if (Array.isArray(val)) return val.join(", ") || "-"
    return val || "-"
  }

  function getPortalList(val: string[] | string | undefined): string[] {
    if (!val) return []
    if (Array.isArray(val)) return val
    return val.split(",").map((s) => s.trim()).filter(Boolean)
  }

  if (loading) {
    return <div className="flex items-center justify-center h-32 text-muted-foreground">불러오는 중...</div>
  }

  if (error) {
    return <div className="flex items-center justify-center h-32 text-destructive">{error}</div>
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <HistoryIcon className="h-10 w-10 text-muted-foreground/30" />
        <p className="text-sm text-muted-foreground">키워드 검색 히스토리가 없습니다.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-bold text-foreground">키워드 검색 히스토리</h2>
      <div className="flex flex-col gap-3">
        {items.map((item, index) => {
          const portalList = getPortalList(item.portals)
          const isExpanded = expandedId === item.id
          const itemSessions = sessions[item.id] ?? []

          return (
            <div
              key={item.id}
              className="rounded-xl border border-border/50 bg-card animate-fade-up overflow-hidden"
              style={{ "--delay": `${index * 50}ms` } as React.CSSProperties}
            >
              {/* Header row */}
              <div
                className="card-hover px-4 py-3 flex items-center cursor-pointer"
                onClick={() => toggleExpand(item.id)}
              >
                {/* Expand icon */}
                <div className="mr-2 text-muted-foreground">
                  {isExpanded
                    ? <ChevronDown className="h-4 w-4" />
                    : <ChevronRight className="h-4 w-4" />}
                </div>

                {/* Left: keyword, mode, portals */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {formatKeywords(item.keywords)}
                  </p>
                  {item.mode && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                      {item.mode}
                    </span>
                  )}
                  <div className="flex gap-1 flex-shrink-0">
                    {portalList.map((p) =>
                      PORTAL_IMGS[p] ? (
                        <img key={p} src={PORTAL_IMGS[p]} alt={PORTAL_LABELS[p] ?? p} title={PORTAL_LABELS[p] ?? p} className="h-5 w-5 rounded object-cover" />
                      ) : null
                    )}
                  </div>
                </div>

                {/* Right: method, date, download, delete */}
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-muted-foreground">
                    {item.interval_minutes ? `${item.interval_minutes}분 간격` : "즉시 수집"}
                  </span>
                  <span className="text-xs text-muted-foreground w-[150px] text-right">
                    {item.created_at ? new Date(item.created_at).toLocaleString("ko-KR") : "-"}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-primary transition-colors"
                    onClick={(e) => { e.stopPropagation(); exportCsv({ history_id: item.id }) }}
                    title="전체 다운로드"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive transition-colors"
                    onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {/* Sessions accordion */}
              {isExpanded && (
                <div className="border-t border-border/30 bg-secondary/30 px-4 py-2">
                  {loadingSessions === item.id && (
                    <p className="text-xs text-muted-foreground py-2">회차 목록 불러오는 중...</p>
                  )}
                  {loadingSessions !== item.id && itemSessions.length === 0 && (
                    <p className="text-xs text-muted-foreground py-2">수집 회차가 없습니다.</p>
                  )}
                  {itemSessions.map((session, si) => (
                    <div
                      key={session.id}
                      className="flex items-center gap-3 py-2 border-b border-border/20 last:border-b-0"
                    >
                      <span className="text-xs font-medium text-foreground w-16">
                        {si + 1}회차
                      </span>
                      <span className="text-xs text-muted-foreground">
                        신규 {session.new_count}건 / 전체 {session.total_count}건
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {session.started_at ? new Date(session.started_at).toLocaleString("ko-KR") : ""}
                      </span>
                      <div className="flex-1" />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-primary"
                        onClick={() => onViewSession?.(session.id)}
                        title="기사 보기"
                      >
                        <Eye className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-primary"
                        onClick={() => exportCsv({ session_id: session.id })}
                        title="회차별 다운로드"
                      >
                        <Download className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

**Step 2: 커밋**

```bash
git add frontend/src/components/History.tsx
git commit -m "feat: 히스토리에 아코디언 회차 조회 + 전체/회차별 다운로드 추가"
```

---

## Task 15: 통합 테스트 — 전체 기능 동작 확인

**Step 1: 백엔드 서버 실행**

Run: `cd /Users/yjs/IdeaProjects/news_crawling/backend && uvicorn main:app --reload --port 8000`

**Step 2: 프론트엔드 개발 서버 실행**

Run: `cd /Users/yjs/IdeaProjects/news_crawling/frontend && npm run dev`

**Step 3: 수동 테스트 체크리스트**

1. AND/OR 토글이 사이드바에 표시되는지 확인
2. AND 모드로 키워드 2개 입력 후 즉시 수집 → 모든 키워드 포함 기사만 수집되는지 확인
3. 기사 목록에서 정렬 기준(수집일/발행일) 변경, 오름차순/내림차순 토글 확인
4. 기사 제목 클릭 → 시스템 기본 브라우저에서 열리는지 확인
5. 기사 카드에 URL 도메인 텍스트 표시 확인
6. 히스토리 탭에서 항목 클릭 → 회차 목록 펼침 확인
7. 회차별 "기사 보기" 클릭 → 기사 목록 탭 전환 + 해당 회차 기사만 표시 확인
8. "필터 해제" 클릭 → 전체 기사로 복귀 확인
9. 히스토리 전체 다운로드 버튼 → CSV 다운로드 확인 (제목, 날짜, 언론사, 링크 4개 컬럼)
10. 회차별 다운로드 버튼 → 해당 회차 기사만 CSV로 다운로드 확인

**Step 4: 최종 커밋**

```bash
git add -A
git commit -m "feat: 5가지 기능 개선 완료 - AND/OR, 정렬, 시스템브라우저, 회차조회, 다운로드"
```
