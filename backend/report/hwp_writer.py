"""
HWP 파일 생성 모듈 — 템플릿 기반 OLE 수정 방식.

HWP 바이너리 포맷은 복잡하므로, 보수적 접근:
  - 템플릿 HWP를 복사한 뒤 PrvText(미리보기 텍스트) 스트림만 교체
  - BodyText 레코드 재구성은 위험하므로 하지 않음
  - .txt 폴백을 항상 함께 저장
"""

import logging
import os
import re
import shutil
import struct
import zlib
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HWP 바이너리 읽기 유틸
# ---------------------------------------------------------------------------

HWPTAG_PARA_TEXT = 67  # 16 (HWPTAG_BEGIN) + 51

# 16바이트 확장 제어문자 코드
_CTRL_EXTEND_16 = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}


def _read_hwp_body_text(ole) -> bytes:
    """OLE 파일에서 BodyText/Section0 스트림을 읽어 반환한다.

    FileHeader의 플래그(offset 36)에서 압축 여부를 확인하고,
    압축되어 있으면 zlib raw-deflate로 해제한다.
    """
    # FileHeader에서 압축 플래그 확인
    header_data = ole.openstream("FileHeader").read()
    compressed = bool(header_data[36] & 1)

    raw = ole.openstream("BodyText/Section0").read()

    if compressed:
        return zlib.decompress(raw, -15)
    return raw


def _extract_text_from_records(data: bytes) -> str:
    """HWP 바이너리 레코드 스트림에서 텍스트를 추출한다.

    레코드 헤더(4바이트): tag_id(10bit) | level(10bit) | size(12bit)
    size == 0xFFF 이면 다음 4바이트가 실제 크기.
    HWPTAG_PARA_TEXT(67) 레코드에서 UTF-16LE 텍스트를 디코딩한다.
    """
    pos = 0
    text_parts: list[str] = []

    while pos + 4 <= len(data):
        header_val = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        tag_id = header_val & 0x3FF
        size = (header_val >> 20) & 0xFFF

        if size == 0xFFF:
            if pos + 4 > len(data):
                break
            size = struct.unpack_from("<I", data, pos)[0]
            pos += 4

        if pos + size > len(data):
            break

        if tag_id == HWPTAG_PARA_TEXT:
            record_data = data[pos : pos + size]
            text_parts.append(_decode_para_text(record_data))

        pos += size

    return "\n".join(text_parts)


def _decode_para_text(record_data: bytes) -> str:
    """HWPTAG_PARA_TEXT 레코드 바이트를 텍스트로 디코딩한다."""
    result: list[str] = []
    i = 0
    length = len(record_data)

    while i + 1 < length:
        char_code = struct.unpack_from("<H", record_data, i)[0]

        if char_code < 32:
            if char_code in _CTRL_EXTEND_16:
                # 16바이트 확장 제어문자: 2(현재) + 14(추가) = 16바이트 건너뜀
                i += 16
            elif char_code == 9:  # tab
                result.append("\t")
                i += 16
            elif char_code == 10:  # LF
                result.append("\n")
                i += 2
            elif char_code == 13:  # CR
                result.append("\n")
                i += 2
            else:
                i += 2
        else:
            result.append(chr(char_code))
            i += 2

    return "".join(result)


# ---------------------------------------------------------------------------
# 보고서 텍스트 생성
# ---------------------------------------------------------------------------

_WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

# 헤더 날짜 패턴: "2026년 4월 16일", "2026 년 4 월 16 일 (수)" 등 허용
_DATE_PATTERN = re.compile(r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일[^\n]*")


def _format_header_date(date_str: str) -> str:
    """헤더용 날짜 문자열 포맷: '2026년 4월 16일 (수)'"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = _WEEKDAY_KR[dt.weekday()]
    return f"{dt.year}년 {dt.month}월 {dt.day}일 ({weekday})"


def _replace_date_in_header(header_elem, date_str: str, hp_ns: str) -> bool:
    """헤더 paragraph(p0) 내부의 <hp:t> 텍스트 중 날짜 패턴을 실제 날짜로 교체.

    템플릿 타이틀 박스 안에 박힌 샘플 날짜를 실행 시점 날짜로 바꾸기 위함.
    """
    new_date = _format_header_date(date_str)
    replaced = False
    for t in header_elem.iter(f"{{{hp_ns}}}t"):
        if t.text and _DATE_PATTERN.search(t.text):
            t.text = _DATE_PATTERN.sub(new_date, t.text)
            replaced = True
    return replaced


def _find_dashed_border_fill_id(header_xml_str: str) -> str:
    """header.xml에서 가장 많은 DASH 테두리를 가진 borderFill id를 찾는다.

    템플릿에 따라 점선 borderFill의 id가 달라질 수 있으므로 동적으로 탐색.
    4방(좌/우/상/하) 모두 DASH인 borderFill을 우선 선택.
    """
    import re as _re
    best_id = None
    best_count = 0
    for m in _re.finditer(
        r'<hh:borderFill id="(\d+)"[^>]*>(.*?)</hh:borderFill>',
        header_xml_str,
        _re.DOTALL,
    ):
        fid = m.group(1)
        body = m.group(2)
        dash_count = body.count('type="DASH"')
        # 4방 모두 DASH인 것을 최우선
        if dash_count >= 4:
            return fid
        if dash_count > best_count:
            best_count = dash_count
            best_id = fid
    return best_id or "1"


def _apply_page_border(header_elem, border_fill_id: str, hp_ns: str) -> int:
    """p0 secPr 내부의 모든 <hp:pageBorderFill>의 borderFillIDRef를 교체.

    원본 템플릿의 pageBorderFill은 id=1(NONE)을 가리켜 페이지 테두리가 없음.
    점선 borderFill id로 바꿔 페이지 전체에 점선 테두리를 적용한다.
    """
    count = 0
    for pbf in header_elem.iter(f"{{{hp_ns}}}pageBorderFill"):
        pbf.set("borderFillIDRef", border_fill_id)
        count += 1
    return count


def generate_text_report(
    date_str: str,
    overview: str,
    editorials: str,
    category_details: dict[str, str],
) -> str:
    """보고서 전체 텍스트를 양식에 맞춰 조합한다.

    Args:
        date_str: 날짜 문자열 (예: "2026-04-16")
        overview: 주요 뉴스 요약 텍스트
        editorials: 금일 사설 텍스트
        category_details: 카테고리별 상세 딕셔너리 (예: {"경제": "ㅇ 경제 내용"})

    Returns:
        완성된 보고서 텍스트
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_kr = _WEEKDAY_KR[dt.weekday()]

    lines: list[str] = []

    # ── 헤더 ──
    lines.append(f"{dt.year}년 {dt.month}월 {dt.day}일 ({weekday_kr})")
    lines.append("")
    lines.append("정책 보도 일일 종합")
    lines.append("")
    lines.append("=" * 60)

    # ── 주요 뉴스 요약 ──
    lines.append("")
    lines.append("■ 주요 뉴스 요약")
    lines.append("")
    lines.append(overview)

    # ── 금일 사설 ──
    lines.append("")
    lines.append("=" * 60)
    lines.append("")
    lines.append("■ 금일 사설")
    lines.append("")
    lines.append(editorials)

    # ── 카테고리별 상세 ──
    if category_details:
        lines.append("")
        lines.append("=" * 60)
        lines.append("")
        lines.append("■ 카테고리별 상세")

        for category, detail in category_details.items():
            lines.append("")
            lines.append(f"▶ {category}")
            lines.append("")
            lines.append(detail)

    lines.append("")
    lines.append("=" * 60)
    lines.append("// END //")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HWP 파일 생성 (템플릿 기반)
# ---------------------------------------------------------------------------


def generate_hwp_from_template(
    template_path: str,
    output_path: str,
    report_text: str,
    date_str: str,
) -> bool:
    """템플릿 HWP를 복사한 뒤 PrvText 스트림만 교체하여 저장한다.

    BodyText 레코드를 재구성하지 않고, PrvText(미리보기 텍스트)만
    교체하는 보수적 접근 방식이다.

    Args:
        template_path: 템플릿 HWP 파일 경로
        output_path: 출력 HWP 파일 경로
        report_text: 보고서 텍스트
        date_str: 날짜 문자열

    Returns:
        성공 시 True, 실패 시 False
    """
    try:
        import olefile
    except ImportError:
        logger.error("olefile 패키지가 설치되어 있지 않습니다: pip install olefile")
        return False

    if not os.path.exists(template_path):
        logger.error(f"템플릿 파일을 찾을 수 없습니다: {template_path}")
        return False

    try:
        # 템플릿 복사
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(template_path, output_path)

        # OLE 파일 열어서 PrvText 스트림 교체
        # olefile.write_stream은 기존 스트림과 동일한 크기만 허용하므로
        # 원본 크기에 맞춰 자르거나 null 패딩한다.
        ole = olefile.OleFileIO(output_path, write_mode=True)
        try:
            if ole.exists("PrvText"):
                original_data = ole.openstream("PrvText").read()
                original_size = len(original_data)

                prv_text_encoded = report_text.encode("utf-16-le")

                if len(prv_text_encoded) > original_size:
                    # 원본보다 크면 잘라냄
                    prv_text_encoded = prv_text_encoded[:original_size]
                elif len(prv_text_encoded) < original_size:
                    # 원본보다 작으면 null 패딩
                    prv_text_encoded += b"\x00" * (original_size - len(prv_text_encoded))

                ole.write_stream("PrvText", prv_text_encoded)
                logger.info(
                    f"HWP PrvText 스트림 교체 완료: {output_path} "
                    f"(원본 {original_size}B, 텍스트 {len(report_text)}자)"
                )
            else:
                logger.warning("PrvText 스트림이 템플릿에 존재하지 않습니다")
        finally:
            ole.close()

        return True

    except Exception as e:
        logger.error(f"HWP 생성 실패: {e}")
        # 실패 시 불완전한 파일 제거
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        return False


# ---------------------------------------------------------------------------
# HWPX 파일 생성 (XML 기반 — 본문 교체 가능)
# ---------------------------------------------------------------------------

# HWPX 네임스페이스
_HWPX_NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}
# 원본 템플릿에서 추출한 스타일 매핑 (paraPrIDRef, charPrIDRef)
_STYLES = {
    "date":         ("20", "17"),   # 날짜
    "title":        ("19", "13"),   # 정책 보도 일일 종합
    "subtitle":     ("18", "14"),   # 종합·경제지 12사, 방송 7사
    "category":     ("13", "7"),    # 카테고리 헤더 (굵은 제목)
    "section":      ("17", "18"),   # □ 소제목
    "bullet":       ("17", "19"),   # ㅇ 본문 불릿
    "sub_bullet":   ("27", "9"),    # - 서브 불릿
    "editorial_h":  ("21", "22"),   # 금일 사설 헤더
    "editorial":    ("22", "26"),   # ￭ 사설 불릿
    "eval":         ("39", "19"),   # (평가)
    "opinion":      ("61", "31"),   # (사설)
    "blank":        ("26", "9"),    # 빈 줄
    "body":         ("26", "9"),    # 일반 본문
}


def _detect_style(line: str) -> tuple:
    """텍스트 줄의 내용을 분석하여 적절한 HWPX 스타일을 반환한다."""
    stripped = line.strip()

    if not stripped:
        return _STYLES["blank"]
    # 구분선 무시
    if stripped.startswith("=") or stripped == "---" or stripped == "// END //":
        return _STYLES["blank"]
    # 헤더
    if stripped.startswith("정책 보도 일일 종합"):
        return _STYLES["title"]
    if stripped.startswith("종합") and "방송" in stripped:
        return _STYLES["subtitle"]
    if stripped.startswith("국민소통실"):
        return _STYLES["subtitle"]
    if "년" in stripped and "월" in stripped and "일" in stripped and len(stripped) < 30:
        return _STYLES["date"]
    # 섹션 헤더
    if stripped.startswith("■"):
        return _STYLES["editorial_h"]
    if stripped.startswith("▶"):
        return _STYLES["category"]
    # 마크다운 볼드로 된 카테고리명 (AI 출력 패턴)
    if stripped.startswith("**") and stripped.endswith("**"):
        return _STYLES["category"]
    if stripped.startswith("□"):
        return _STYLES["section"]
    # 사설
    if stripped.startswith("￭"):
        return _STYLES["editorial"]
    # 불릿
    if stripped.startswith("ㅇ") and "(평가)" in stripped:
        return _STYLES["eval"]
    if stripped.startswith("ㅇ") and "(사설)" in stripped:
        return _STYLES["opinion"]
    if stripped.startswith("ㅇ"):
        return _STYLES["bullet"]
    # 서브불릿
    if stripped.startswith("-") or stripped.startswith("  -") or stripped.startswith("   -"):
        return _STYLES["sub_bullet"]
    # 마크다운 서브헤더 (AI 출력 패턴)
    if stripped.startswith("###"):
        return _STYLES["section"]
    if stripped.startswith("##"):
        return _STYLES["category"]

    return _STYLES["body"]


def _clone_and_replace(template, new_text: str, new_id: int, hp_ns: str):
    """템플릿 paragraph를 deep copy하고 모든 <t> 텍스트를 교체한다."""
    import copy
    p = copy.deepcopy(template)
    p.set("id", str(new_id))

    # linesegarray 제거 (텍스트 길이 변경 대응)
    for lsa in p.findall(f"{{{hp_ns}}}linesegarray"):
        p.remove(lsa)

    # 모든 <t> 요소: 첫 번째에만 텍스트, 나머지 비우기
    t_elems = list(p.iter(f"{{{hp_ns}}}t"))
    for i, t in enumerate(t_elems):
        t.text = new_text if i == 0 else ""

    return p


def generate_hwpx_from_template(
    template_path: str,
    output_path: str,
    report_text: str,
    date_str: str,
) -> bool:
    """python-hwpx 라이브러리로 HWPX 템플릿의 본문을 교체한다.

    원본 paragraph를 deep copy하여 서식(글꼴, 크기, 색상, 테이블 박스 등)을 보존.
    - p0 (타이틀 박스 + 페이지설정): 그대로 유지
    - p1 (빈 줄): 유지
    - p3~ (본문): 패턴 복제 + 텍스트 교체

    Args:
        template_path: 템플릿 HWPX 파일 경로
        output_path: 출력 HWPX 파일 경로
        report_text: 보고서 텍스트
        date_str: 날짜 문자열

    Returns:
        성공 시 True, 실패 시 False
    """
    try:
        from hwpx import HwpxPackage
    except ImportError:
        logger.error("python-hwpx 패키지가 필요합니다: pip install python-hwpx")
        return False

    import copy

    if not os.path.exists(template_path):
        logger.error(f"HWPX 템플릿 파일을 찾을 수 없습니다: {template_path}")
        return False

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        hp_ns = _HWPX_NS["hp"]

        # 1. 템플릿 열기
        pkg = HwpxPackage.open(template_path)
        section_path = pkg.section_paths()[0]
        section = pkg.get_xml(section_path)

        # 1.1 점선 테두리 borderFill id 탐색 (header.xml에서)
        try:
            header_paths = pkg.header_paths() if hasattr(pkg, "header_paths") else []
            header_xml_str = ""
            if header_paths:
                from xml.etree import ElementTree as ET
                header_xml_str = ET.tostring(pkg.get_xml(header_paths[0]), encoding="unicode")
            # fallback: raw zip read (python-hwpx가 header 접근 방식이 다를 수 있음)
            if not header_xml_str:
                import zipfile as _zip
                with _zip.ZipFile(template_path) as _z:
                    header_xml_str = _z.read("Contents/header.xml").decode("utf-8")
            dashed_id = _find_dashed_border_fill_id(header_xml_str)
            logger.info(f"점선 borderFill id 탐색 결과: {dashed_id}")
        except Exception as e:
            logger.warning(f"점선 borderFill id 탐색 실패, 기본값 '6' 사용: {e}")
            dashed_id = "6"

        orig_paragraphs = section.findall(f"{{{hp_ns}}}p")
        if len(orig_paragraphs) < 26:
            logger.error(f"템플릿 paragraph 수가 부족합니다: {len(orig_paragraphs)}")
            return False

        # 2. 템플릿 paragraph 패턴 수집 (deep copy용)
        tpl_header = orig_paragraphs[0]       # 타이틀 박스 (secPr + tbl)
        tpl_blank_h = orig_paragraphs[1]      # 헤더 뒤 빈줄
        tpl_cat_header = orig_paragraphs[3]   # 카테고리 헤더 (tbl 포함, 서식 박스)
        tpl_bullet = orig_paragraphs[4]       # ㅇ 불릿
        tpl_sub = orig_paragraphs[5]          # - 서브불릿
        tpl_eval = orig_paragraphs[11]        # ㅇ (평가)
        tpl_opinion = orig_paragraphs[17]     # ㅇ (사설)
        tpl_blank = orig_paragraphs[25]       # 빈 줄

        # 3. 기존 paragraph 모두 제거
        for p in orig_paragraphs:
            section.remove(p)

        # 4. 헤더 유지 (p0 + p1) — 날짜 교체 + 페이지 점선 테두리 적용
        header_copy = copy.deepcopy(tpl_header)
        if _replace_date_in_header(header_copy, date_str, hp_ns):
            logger.info(f"헤더 날짜 교체: {_format_header_date(date_str)}")
        else:
            logger.warning("헤더에서 날짜 패턴을 찾지 못했습니다 (템플릿 확인 필요)")
        # 페이지 점선 테두리 적용 (pageBorderFill 참조를 dashed borderFill id로 교체)
        pbf_count = _apply_page_border(header_copy, dashed_id, hp_ns)
        if pbf_count > 0:
            logger.info(f"페이지 점선 테두리 적용: pageBorderFill {pbf_count}개 → borderFillIDRef={dashed_id}")
        section.append(header_copy)
        section.append(copy.deepcopy(tpl_blank_h))

        # 5. 보고서 텍스트를 paragraph로 변환
        lines = report_text.split("\n")
        pid = 10

        for line in lines:
            stripped = line.strip()

            # 스킵
            if stripped.startswith("정책 보도 일일 종합"):
                continue
            if "년" in stripped and "월" in stripped and "일" in stripped and len(stripped) < 30:
                continue

            # 빈 줄 / 구분선
            if not stripped or stripped.startswith("=") or stripped == "---" or stripped == "// END //":
                section.append(_clone_and_replace(tpl_blank, "", pid, hp_ns))
            # 카테고리/섹션 헤더
            elif stripped.startswith("▶") or stripped.startswith("■"):
                header_text = stripped.lstrip("▶■ ")
                section.append(_clone_and_replace(tpl_cat_header, header_text, pid, hp_ns))
            # ㅇ (평가)
            elif stripped.startswith("ㅇ") and "(평가)" in stripped:
                section.append(_clone_and_replace(tpl_eval, line, pid, hp_ns))
            # ㅇ (사설)
            elif stripped.startswith("ㅇ") and "(사설)" in stripped:
                section.append(_clone_and_replace(tpl_opinion, line, pid, hp_ns))
            # ㅇ 불릿
            elif stripped.startswith("ㅇ"):
                section.append(_clone_and_replace(tpl_bullet, line, pid, hp_ns))
            # ￭ 사설 불릿
            elif stripped.startswith("￭"):
                section.append(_clone_and_replace(tpl_bullet, line, pid, hp_ns))
            # - 서브불릿
            elif stripped.startswith("-") or stripped.startswith("  -"):
                section.append(_clone_and_replace(tpl_sub, line, pid, hp_ns))
            # 일반 본문
            else:
                section.append(_clone_and_replace(tpl_blank, line, pid, hp_ns))

            pid += 1

        # 6. 수정된 section 저장
        pkg.set_xml(section_path, section)
        pkg.save(output_path)

        logger.info(f"HWPX 보고서 생성 완료: {output_path} ({pid - 10}개 paragraph)")
        return True

    except Exception as e:
        logger.error(f"HWPX 생성 실패: {e}", exc_info=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        return False


# ---------------------------------------------------------------------------
# 텍스트 보고서 저장 (폴백)
# ---------------------------------------------------------------------------


def save_text_report(output_path: str, report_text: str) -> bool:
    """보고서를 .txt 파일로 저장한다. HWP 생성 실패 시 폴백으로 사용.

    Args:
        output_path: 출력 파일 경로
        report_text: 보고서 텍스트

    Returns:
        성공 시 True, 실패 시 False
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info(f"텍스트 보고서 저장 완료: {output_path}")
        return True
    except Exception as e:
        logger.error(f"텍스트 보고서 저장 실패: {e}")
        return False
