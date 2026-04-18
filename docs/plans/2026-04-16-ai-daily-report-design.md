# AI 일일 동향 보고서 생성 기능 설계

## 개요

수집된 뉴스 기사를 AI(`claude -p`)로 카테고리별 자동 분류 및 요약하여, 기존 HWP 양식과 동일한 구조의 "정책 보도 일일 종합" 보고서를 자동 생성하는 기능.

## 요구사항

- 수집된 기사 본문을 URL에서 크롤링하여 읽어옴
- AI가 기사를 주제별로 자동 분류
- 카테고리별 요약을 샘플 양식 스타일로 생성
- 최종 출력: HWP 파일 (기존 양식 템플릿 기반)
- AI 엔진: `claude -p` (Claude Code CLI 파이프 모드)

## 보고서 양식 구조 (샘플 기반)

```
1. 헤더: 날짜, 제목("정책 보도 일일 종합"), 매체 수, 기관명
2. 주요 뉴스 요약 (ㅇ 불릿, 카테고리별 핵심 1~2줄)
3. 금일 사설 (￭ 불릿, 주제별 사설 요약)
4. 카테고리별 상세 보도
   - 카테고리명 (예: 경제, 외교안보, 사회 등)
     - ㅇ (주요 내용) 핵심 보도 요약
     - (평가) 의미/맥락 분석
     - (사설) 관련 사설 요약
```

## 아키텍처

### 전체 흐름

```
[프론트엔드] "보고서 생성" 버튼
    ↓
[POST /api/report/generate] 생성 요청 (날짜, 키워드 옵션)
    ↓
[report/generator.py] 오케스트레이터
    ├─ 1. DB에서 해당 날짜 기사 목록 조회
    ├─ 2. article_scraper.py → 각 기사 URL 방문, 본문 크롤링
    ├─ 3. ai_summarizer.py → claude -p 호출
    │    ├─ Step 1: 카테고리 분류 (기사 제목+본문 → 주제별 그룹핑)
    │    └─ Step 2: 카테고리별 요약 생성 (양식 스타일 맞춤)
    ├─ 4. hwp_writer.py → HWP 템플릿에 내용 삽입
    └─ 5. 완성된 HWP 파일 저장
    ↓
[프론트엔드] 진행 상태 폴링 → 완료 시 다운로드 링크
```

### 백엔드 모듈

#### `backend/report/generator.py` — 오케스트레이터
- `generate_report(date, keywords?)` 메인 함수
- 비동기 실행 (쓰레드 풀), 상태 추적
- 진행 단계: `fetching_articles` → `scraping_content` → `ai_classifying` → `ai_summarizing` → `generating_hwp` → `completed`

#### `backend/report/article_scraper.py` — 기사 본문 크롤링
- 기존 `crawlers/` 모듈의 requests + BeautifulSoup 패턴 재사용
- 기사 URL → 본문 텍스트 추출 (newspaper3k 또는 직접 파싱)
- 병렬 크롤링 (ThreadPoolExecutor, max_workers=5)
- 실패 시 제목+설명만으로 폴백

#### `backend/report/ai_summarizer.py` — Claude CLI 호출
- **CLI 확인**: 초기화 시 `claude --version` 실행하여 설치 여부 체크
- **1단계 - 분류**: 기사 목록(제목+본문 앞부분)을 JSON으로 전달 → 카테고리별 그룹 반환
- **2단계 - 요약**: 카테고리별 기사 본문 전달 → 양식에 맞는 요약 텍스트 생성
- 프롬프트에 샘플 양식 구조 포함하여 스타일 일관성 유도
- `subprocess.run(["claude", "-p", prompt], input=data, capture_output=True)`

#### `backend/report/hwp_writer.py` — HWP 파일 생성
- **1차 시도**: 템플릿 기반 OLE 조작 (`olefile` + `zlib`)
  - 기존 HWP 파일의 BodyText/Section0 스트림 디코딩
  - 텍스트 레코드(HWPTAG_PARA_TEXT) 교체
  - 서식(글꼴, 크기, 정렬) 유지
- **폴백**: 구현이 어려울 경우
  - HWPX(XML 기반) 직접 생성, 또는
  - python-docx로 DOCX 생성 후 변환 안내

#### `backend/api/report.py` — REST 엔드포인트
- `POST /api/report/generate` — 생성 시작 (날짜, 키워드 필터 옵션)
- `GET /api/report/status` — 진행 상태 + `cli_available` 플래그
- `GET /api/report/download/{filename}` — HWP 파일 다운로드
- `GET /api/report/list` — 생성된 보고서 목록

### 프론트엔드

#### 새 컴포넌트: `components/ReportGenerator.tsx`
- App.tsx 탭에 "보고서" 탭 추가
- 날짜 선택 (기본: 오늘)
- "보고서 생성" 버튼
- 진행 상태 표시 (단계별 프로그레스)
- 생성 완료 시 다운로드 버튼
- 이전 보고서 목록

#### CLI 미설치 시 안내
- `cli_available: false`이면 보고서 생성 버튼 비활성화
- "Claude CLI가 필요합니다" 안내 메시지 + 설치 링크

### AI 프롬프트 설계

#### 분류 프롬프트 (Step 1)
```
다음 뉴스 기사들을 주제별로 분류해주세요.
카테고리는 기사 내용에 따라 자동으로 생성하되,
정책/정치, 경제, 외교안보, 사회, 과학기술 등 대분류로 묶어주세요.

출력 형식: JSON
{
  "categories": [
    {"name": "카테고리명", "article_ids": [1, 3, 5]}
  ]
}
```

#### 요약 프롬프트 (Step 2)
```
다음은 '{카테고리명}' 관련 뉴스 기사입니다.
아래 양식에 맞춰 요약해주세요:

[양식]
ㅇ (주요 내용) 핵심 보도 1~3줄 요약. 보도 매체명 괄호 표기
  - 세부 내용 불릿
ㅇ (평가) 의미/맥락 1~2줄
ㅇ (사설) 관련 사설이 있으면 요약

톤: 객관적, 간결한 보고서 스타일
```

### 파일 저장 위치
- 템플릿: `backend/report/templates/daily_report_template.hwp`
- 생성된 보고서: `backend/data/reports/YYMMDD_정책보도_일일종합.hwp`

### 의존성 추가
- `olefile` — HWP OLE 파싱
- `newspaper3k` 또는 직접 구현 — 기사 본문 추출

## 기술적 리스크

1. **HWP OLE 텍스트 교체**: 바이너리 레코드 재구성이 필요하며, 서식 유지가 까다로울 수 있음 → 폴백으로 HWPX 또는 DOCX 방안 준비
2. **기사 본문 크롤링 실패**: 일부 언론사 접근 차단 가능 → 제목+설명으로 폴백
3. **claude -p 응답 크기**: 기사가 많으면 입력 토큰 한계 → 카테고리별 분할 호출
4. **CLI 미설치 환경**: 명확한 안내 UI 필요
