"""AI 요약 모듈 — Claude CLI(claude -p) 파이프 모드를 사용한 뉴스 기사 분류 및 요약."""

import json
import logging
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Claude CLI 경로 캐시
_claude_path_cache: Optional[str] = None


def _find_claude_path() -> Optional[str]:
    """Claude CLI 경로를 찾는다. shutil.which 실패 시 일반적인 설치 경로도 탐색."""
    global _claude_path_cache
    if _claude_path_cache and os.path.isfile(_claude_path_cache):
        return _claude_path_cache

    # 1차: shutil.which
    path = shutil.which("claude")
    if path:
        _claude_path_cache = path
        return path

    # 2차: 일반적인 설치 경로 탐색 (nvm, homebrew, global npm 등)
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".nvm/versions/node"),  # nvm 하위 검색
        "/usr/local/bin",
        os.path.join(home, ".local/bin"),
        os.path.join(home, ".bun/bin"),
    ]

    # nvm 경로는 버전별로 있으므로 하위 탐색
    nvm_base = os.path.join(home, ".nvm/versions/node")
    if os.path.isdir(nvm_base):
        for version_dir in sorted(os.listdir(nvm_base), reverse=True):
            candidate = os.path.join(nvm_base, version_dir, "bin", "claude")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                _claude_path_cache = candidate
                logger.info(f"Claude CLI 발견 (nvm): {candidate}")
                return candidate

    for base in candidates:
        candidate = os.path.join(base, "claude")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            _claude_path_cache = candidate
            logger.info(f"Claude CLI 발견: {candidate}")
            return candidate

    return None


def check_cli_available() -> Tuple[bool, str]:
    """Claude CLI 설치 여부를 확인하고 버전 정보를 반환한다.

    Returns:
        (True, version_string) — CLI가 정상 동작할 때
        (False, error_message) — CLI가 없거나 실행 실패 시
    """
    path = _find_claude_path()
    if not path:
        return False, "Claude CLI가 설치되어 있지 않습니다. 'npm install -g @anthropic-ai/claude-code' 로 설치하세요."

    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            return True, version
        return False, f"Claude CLI 실행 실패 (exit {result.returncode}): {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Claude CLI 버전 확인 타임아웃 (10초)"
    except Exception as e:
        return False, f"Claude CLI 실행 중 오류: {e}"


def _call_claude(prompt: str, input_data: str, timeout: int = 300) -> Optional[str]:
    """Claude CLI를 파이프 모드(-p)로 호출한다.

    Args:
        prompt: 시스템 프롬프트 (claude -p 인자)
        input_data: stdin으로 전달할 데이터
        timeout: 최대 대기 시간(초)

    Returns:
        Claude 응답 텍스트, 실패 시 None
    """
    path = _find_claude_path()
    if not path:
        logger.error("Claude CLI를 찾을 수 없습니다. PATH 및 일반 설치 경로 모두 검색 실패.")
        return None

    try:
        result = subprocess.run(
            [path, "-p", prompt],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.error(f"Claude CLI 오류 (exit {result.returncode}): {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Claude CLI 호출 타임아웃 ({timeout}초)")
        return None
    except Exception as e:
        logger.error(f"Claude CLI 호출 중 오류: {e}")
        return None


def _strip_code_block(text: str) -> str:
    """마크다운 코드블록(```json ... ``` 등)을 제거하고 내부 텍스트만 반환한다."""
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def classify_articles(articles: List[Dict]) -> Optional[Dict]:
    """기사 목록을 카테고리별로 분류한다.

    Args:
        articles: 기사 딕셔너리 리스트. 각 항목에 id, title, publisher,
                  content(또는 preview/description) 키가 있어야 한다.

    Returns:
        {"categories": [{"name": "카테고리명", "article_ids": [0, 2, 5]}, ...]}
        실패 시 None
    """
    if not articles:
        logger.warning("분류할 기사가 없습니다.")
        return None

    # 토큰 절약을 위해 content 500자, description 300자까지만 전달
    compact = []
    for i, a in enumerate(articles):
        item = {
            "id": i,
            "title": a.get("title", ""),
            "publisher": a.get("publisher", ""),
        }
        content = a.get("content", "")
        description = a.get("description", "") or a.get("preview", "")
        if content:
            item["content"] = content[:500]
        if description:
            item["description"] = description[:300]
        compact.append(item)

    prompt = (
        "당신은 뉴스 기사 분류 전문가입니다. "
        "아래 JSON 배열로 제공되는 기사들을 주제별 카테고리로 분류하세요. "
        "카테고리는 정치, 경제, 사회, 국제, IT/과학, 문화/생활, 스포츠, 사설/칼럼 등 적절한 이름을 사용하되, "
        "기사 내용에 맞게 자유롭게 지정하세요. "
        "결과는 반드시 아래 JSON 형식으로만 출력하세요. 설명이나 부연 없이 JSON만 출력하세요.\n"
        '{"categories": [{"name": "카테고리명", "article_ids": [0, 2, 5]}]}'
    )

    input_data = json.dumps(compact, ensure_ascii=False)
    raw = _call_claude(prompt, input_data)
    if not raw:
        return None

    try:
        cleaned = _strip_code_block(raw)
        result = json.loads(cleaned)
        if "categories" in result:
            return result
        logger.error(f"분류 결과에 'categories' 키가 없습니다: {list(result.keys())}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"분류 결과 JSON 파싱 실패: {e}\n응답: {raw[:500]}")
        return None


def summarize_category(category_name: str, articles: List[Dict]) -> Optional[str]:
    """카테고리별 기사를 요약한다.

    Args:
        category_name: 카테고리 이름 (예: "경제", "정치")
        articles: 해당 카테고리의 기사 리스트. content 키에 본문이 있어야 한다.

    Returns:
        양식화된 요약 텍스트. 실패 시 None.
    """
    if not articles:
        logger.warning(f"요약할 기사가 없습니다: {category_name}")
        return None

    # 기사 본문을 최대 3000자까지 정리
    article_texts = []
    for i, a in enumerate(articles):
        title = a.get("title", "제목 없음")
        publisher = a.get("publisher", "")
        content = a.get("content", "")[:3000]
        article_texts.append(
            f"[기사 {i + 1}] {title} ({publisher})\n{content}"
        )

    prompt = (
        f"당신은 한국 뉴스 브리핑 작성 전문가입니다. "
        f"'{category_name}' 카테고리의 기사들을 아래 양식에 맞춰 요약하세요.\n\n"
        f"양식:\n"
        f"ㅇ (주요 내용) 핵심 사실과 수치를 간결하게 정리\n"
        f"  - 세부 내용이 있으면 하위 항목으로\n"
        f"ㅇ (평가) 해당 이슈의 의미와 영향을 1~2문장으로\n"
        f"ㅇ (사설) 사설이나 칼럼이 포함된 경우 논조를 요약\n\n"
        f"규칙:\n"
        f"- 사실 기반으로만 작성하고 주관적 해석은 피하세요\n"
        f"- 동일 주제 기사는 하나로 통합하세요\n"
        f"- (사설) 항목은 사설/칼럼 기사가 있을 때만 포함하세요\n"
        f"- 양식 기호(ㅇ, -)를 반드시 사용하세요"
    )

    input_data = "\n\n---\n\n".join(article_texts)
    return _call_claude(prompt, input_data)


def generate_full_summary(category_summaries: Dict[str, str], date_str: str) -> Optional[str]:
    """카테고리별 요약을 종합하여 최종 보고서를 생성한다.

    Args:
        category_summaries: {카테고리명: 요약텍스트} 딕셔너리
        date_str: 보고서 날짜 문자열 (예: "2026-04-16")

    Returns:
        '===주요 뉴스 요약===' + '===금일 사설===' 구조의 종합 요약.
        실패 시 None.
    """
    if not category_summaries:
        logger.warning("종합할 카테고리 요약이 없습니다.")
        return None

    summaries_text = ""
    for cat_name, summary in category_summaries.items():
        summaries_text += f"\n[{cat_name}]\n{summary}\n"

    prompt = (
        f"당신은 한국 뉴스 데일리 브리핑 편집자입니다. "
        f"날짜: {date_str}\n\n"
        f"아래 카테고리별 요약을 종합하여 최종 보고서를 작성하세요.\n\n"
        f"출력 형식:\n"
        f"===주요 뉴스 요약===\n"
        f"카테고리별로 핵심 내용을 정리. ㅇ 기호를 사용.\n"
        f"각 카테고리명을 소제목으로 사용하세요.\n\n"
        f"===금일 사설===\n"
        f"사설/칼럼 내용이 있으면 여기에 모아서 정리.\n"
        f"사설이 없으면 이 섹션은 '해당 없음'으로 표기.\n\n"
        f"규칙:\n"
        f"- 구분자 '===' 는 반드시 포함하세요\n"
        f"- 간결하고 읽기 쉽게 작성하세요\n"
        f"- 원본 요약의 사실 관계를 변경하지 마세요"
    )

    return _call_claude(prompt, summaries_text)
