# NewsDesk

네이버, 다음, 네이트 뉴스 포털에서 키워드 기반으로 뉴스 기사를 자동 수집하고 분석하는 데스크톱 애플리케이션입니다.

## 주요 기능

- **멀티 키워드 / 멀티 포털 크롤링** — 여러 키워드를 동시에 설정하고 네이버, 다음, 네이트에서 병렬 수집
- **스케줄 수집** — 15분~24시간 간격으로 자동 반복 수집
- **즉시 수집** — 시작일 지정 가능한 일회성 수집
- **중복 제거** — 제목 유사도 75% 기준 자동 중복 검출, 포털 간 교차 중복 처리
- **통계 대시보드** — 일별 추이, 키워드 분포, 포털별, 언론사별, 시간대별 차트 (ECharts)
- **스크랩** — 관심 기사 북마크 및 관리
- **CSV 내보내기** — 수집된 기사 데이터 다운로드
- **테마** — 다크 5종 + 라이트 3종
- **Windows 배포** — Electron + PyInstaller 기반 설치 프로그램 및 포터블 실행 파일

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | Python, FastAPI, Uvicorn, SQLite (WAL), APScheduler |
| 크롤링 | Requests, BeautifulSoup4, lxml |
| 프론트엔드 | React 19, TypeScript, Vite, Tailwind CSS v4 |
| 차트 | ECharts (echarts-for-react) |
| UI 컴포넌트 | Radix UI, Lucide React |
| 데스크톱 | Electron, electron-builder (NSIS 인스톨러) |
| 빌드 | PyInstaller (백엔드 exe), electron-builder (데스크톱 패키징) |

## 시작하기

### 요구 사항

- Python 3.10+
- Node.js 18+

### 설치

```bash
# Python 의존성 설치
pip install -r requirements.txt

# 프론트엔드 의존성 설치
cd frontend && npm install

# Electron 의존성 설치
cd electron && npm install
```

### 개발 모드 실행

백엔드와 프론트엔드를 각각 실행합니다. 프론트엔드 Vite 개발 서버가 `/api` 요청을 백엔드(8000번 포트)로 프록시합니다.

```bash
# 터미널 1: 백엔드
cd backend && uvicorn main:app --reload --port 8000

# 터미널 2: 프론트엔드
cd frontend && npm run dev
```

Electron 개발 모드로 실행할 수도 있습니다 (백엔드를 자동으로 시작):

```bash
cd electron && npx electron .
```

### 프로덕션 빌드

```bash
# 전체 빌드 (React 빌드 → PyInstaller exe → Electron 패키징)
python build.py
```

빌드 결과물:

| 출력 경로 | 설명 |
|-----------|------|
| `dist/NewsDesk/NewsDesk.exe` | PyInstaller 백엔드 단독 실행 파일 |
| `dist-electron/win-unpacked/NewsDesk.exe` | Electron 포터블 실행 파일 |
| `dist-electron/NewsDesk Setup 1.0.0.exe` | NSIS 설치 프로그램 |

### 간편 실행 (브라우저 모드)

```bash
# FastAPI 서버 시작 + 브라우저 자동 오픈
python launcher.py
```

## 프로젝트 구조

```
news_crawling/
├── backend/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── scheduler.py         # 크롤링 스케줄러
│   ├── api/                 # REST API 엔드포인트
│   │   ├── crawl.py         #   수집 시작/중지/상태
│   │   ├── news.py          #   기사 목록/스크랩/CSV
│   │   ├── stats.py         #   통계 (6종 차트 데이터)
│   │   └── history.py       #   검색 이력
│   ├── crawlers/            # 포털별 크롤러
│   │   ├── base.py          #   추상 베이스 클래스
│   │   ├── naver.py         #   네이버
│   │   ├── daum.py          #   다음
│   │   └── nate.py          #   네이트
│   └── db/
│       └── database.py      # SQLite DB 스키마 및 쿼리
├── frontend/
│   └── src/
│       ├── App.tsx           # 메인 레이아웃 (탭 네비게이션)
│       ├── components/       # UI 컴포넌트
│       │   ├── Sidebar.tsx   #   설정 사이드바
│       │   ├── NewsList.tsx  #   기사 목록 (무한 스크롤)
│       │   ├── Analytics.tsx #   통계 대시보드
│       │   ├── Scraps.tsx    #   스크랩 관리
│       │   ├── History.tsx   #   검색 이력
│       │   └── ui/           #   공통 UI (Button, Input, Select 등)
│       └── hooks/
│           └── useApi.ts     # API 클라이언트
├── electron/
│   ├── main.js              # Electron 메인 프로세스
│   └── package.json         # Electron 의존성 및 빌드 설정
├── assets/                   # 아이콘 리소스 (icon.png, icon.ico)
├── build.py                  # 전체 빌드 스크립트 (프론트엔드 + PyInstaller + Electron)
├── server_entry.py           # Electron용 백엔드 진입점
├── launcher.py               # 런처 (서버 + 브라우저)
└── requirements.txt          # Python 의존성
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/crawl/start` | 스케줄 수집 시작 |
| POST | `/api/crawl/stop` | 수집 중지 |
| POST | `/api/crawl/run-once` | 즉시 1회 수집 |
| GET | `/api/crawl/status` | 수집 상태 조회 |
| GET | `/api/news/list` | 기사 목록 (필터링, 페이징) |
| POST | `/api/news/scrap` | 기사 스크랩 토글 |
| GET | `/api/news/export-csv` | CSV 내보내기 |
| POST | `/api/news/reset` | 전체 데이터 초기화 |
| GET | `/api/stats/*` | 통계 데이터 (daily, keyword, portal, publisher, hourly, article-hourly) |
| GET | `/api/history/list` | 검색 이력 목록 |
| DELETE | `/api/history/{id}` | 검색 이력 삭제 |

## 라이선스

Private
