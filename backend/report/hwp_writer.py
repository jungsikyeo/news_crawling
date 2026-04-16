"""
HWP 파일 생성 모듈 — 템플릿 기반 OLE 수정 방식.

HWP 바이너리 포맷은 복잡하므로, 보수적 접근:
  - 템플릿 HWP를 복사한 뒤 PrvText(미리보기 텍스트) 스트림만 교체
  - BodyText 레코드 재구성은 위험하므로 하지 않음
  - .txt 폴백을 항상 함께 저장
"""

import logging
import os
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


def generate_hwpx_from_template(
    template_path: str,
    output_path: str,
    report_text: str,
    date_str: str,
) -> bool:
    """HWPX 템플릿의 section0.xml 본문을 교체하여 새 파일을 생성한다.

    텍스트 내용을 분석하여 원본 템플릿의 스타일을 자동 매핑한다.

    Args:
        template_path: 템플릿 HWPX 파일 경로
        output_path: 출력 HWPX 파일 경로
        report_text: 보고서 텍스트
        date_str: 날짜 문자열

    Returns:
        성공 시 True, 실패 시 False
    """
    import zipfile
    import xml.etree.ElementTree as ET

    if not os.path.exists(template_path):
        logger.error(f"HWPX 템플릿 파일을 찾을 수 없습니다: {template_path}")
        return False

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 네임스페이스 등록 (출력 시 ns0 방지)
        _all_ns = {
            **_HWPX_NS,
            "ha": "http://www.hancom.co.kr/hwpml/2011/app",
            "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
            "hh": "http://www.hancom.co.kr/hwpml/2011/head",
            "hhs": "http://www.hancom.co.kr/hwpml/2011/history",
            "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
            "hpf": "http://www.hancom.co.kr/schema/2011/hpf",
            "dc": "http://purl.org/dc/elements/1.1/",
            "opf": "http://www.idpf.org/2007/opf/",
            "ooxmlchart": "http://www.hancom.co.kr/hwpml/2016/ooxmlchart",
            "hwpunitchar": "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar",
            "epub": "http://www.idpf.org/2007/ops",
            "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
        }
        for prefix, uri in _all_ns.items():
            ET.register_namespace(prefix, uri)

        # 1. 템플릿 ZIP에서 section0.xml 읽기
        with zipfile.ZipFile(template_path, "r") as zin:
            section_xml = zin.read("Contents/section0.xml")

        # 2. section0.xml 파싱
        root = ET.fromstring(section_xml)
        hp_ns = _HWPX_NS["hp"]

        # 3. 첫 번째 <hp:p>에서 secPr(페이지 설정) 보존
        first_p = root.find(f"{{{hp_ns}}}p")
        sec_pr = None
        if first_p is not None:
            for run in first_p.findall(f"{{{hp_ns}}}run"):
                sp = run.find(f"{{{hp_ns}}}secPr")
                if sp is not None:
                    sec_pr = sp
                    run.remove(sp)
                    break

        # 4. 기존 paragraph 모두 제거
        for p in root.findall(f"{{{hp_ns}}}p"):
            root.remove(p)

        # 5. 보고서 텍스트를 스타일 매핑된 paragraph로 변환
        lines = report_text.split("\n")
        for i, line in enumerate(lines):
            para_pr, char_pr = _detect_style(line)

            p_elem = ET.SubElement(root, f"{{{hp_ns}}}p")
            p_elem.set("id", str(i))
            p_elem.set("paraPrIDRef", para_pr)
            p_elem.set("styleIDRef", "0")
            p_elem.set("pageBreak", "0")
            p_elem.set("columnBreak", "0")
            p_elem.set("merged", "0")

            run_elem = ET.SubElement(p_elem, f"{{{hp_ns}}}run")
            run_elem.set("charPrIDRef", char_pr)

            # 첫 번째 paragraph에 secPr 넣기
            if i == 0 and sec_pr is not None:
                run_elem.insert(0, sec_pr)

            t_elem = ET.SubElement(run_elem, f"{{{hp_ns}}}t")
            t_elem.text = line

        # 6. 수정된 XML을 새 ZIP으로 쓰기
        new_section_xml = ET.tostring(root, encoding="unicode", xml_declaration=True)

        with zipfile.ZipFile(template_path, "r") as zin:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.namelist():
                    if item == "Contents/section0.xml":
                        zout.writestr(item, new_section_xml.encode("utf-8"))
                    elif item == "Preview/PrvText.txt":
                        zout.writestr(item, report_text[:2048].encode("utf-8"))
                    else:
                        zout.writestr(item, zin.read(item))

        logger.info(f"HWPX 보고서 생성 완료: {output_path} ({len(lines)}개 paragraph)")
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
