import os
import re
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from report.generator import REPORTS_DIR

router = APIRouter()

# 업로드 허용 확장자 (한글 보고서만)
_ALLOWED_EXT = (".hwpx", ".hwp")
# 파일 크기 한도 (50MB)
_MAX_UPLOAD_SIZE = 50 * 1024 * 1024
# 안전한 파일명 패턴
_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|]')


class ReportGenerateRequest(BaseModel):
    date: Optional[str] = None
    categories: Optional[str] = None  # 콤마 구분 카테고리 (예: "경제,외교안보,사회")


@router.post("/generate")
def generate_report(req: ReportGenerateRequest, request: Request):
    generator = request.app.state.report_generator
    status = generator.get_status()
    if not status["cli_available"]:
        return {"error": "claude CLI가 설치되어 있지 않습니다.", "cli_message": status["cli_message"]}
    if generator.is_generating:
        return {"error": "보고서 생성이 이미 진행 중입니다."}
    # 콤마 구분 문자열 → 리스트 변환
    cat_list = None
    if req.categories:
        cat_list = [c.strip() for c in req.categories.split(",") if c.strip()]
    generator.generate(date_str=req.date, user_categories=cat_list)
    return {"status": "started", "date": req.date}


@router.get("/status")
def report_status(request: Request):
    generator = request.app.state.report_generator
    return generator.get_status()


@router.get("/list")
def list_reports(request: Request):
    generator = request.app.state.report_generator
    return {"reports": generator.list_reports()}


def _safe_report_path(filename: str) -> str:
    """경로 우회(path traversal)를 차단하고 REPORTS_DIR 내부 파일만 반환."""
    # 파일명만 허용 (경로 구분자 포함 금지)
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명")
    filepath = os.path.join(REPORTS_DIR, filename)
    # 절대 경로 검증
    abs_reports = os.path.abspath(REPORTS_DIR)
    abs_file = os.path.abspath(filepath)
    if not abs_file.startswith(abs_reports + os.sep):
        raise HTTPException(status_code=400, detail="유효하지 않은 경로")
    return filepath


@router.get("/download/{filename}")
def download_report(filename: str, request: Request):
    try:
        filepath = _safe_report_path(filename)
    except HTTPException as e:
        return {"error": e.detail, "filename": filename}
    if not os.path.isfile(filepath):
        return {"error": "파일을 찾을 수 없습니다.", "filename": filename}
    if filename.endswith(".hwpx"):
        media_type = "application/hwp+zip"
    elif filename.endswith(".hwp"):
        media_type = "application/x-hwp"
    else:
        media_type = "text/plain; charset=utf-8"
    return FileResponse(filepath, media_type=media_type, filename=filename)


@router.get("/preview/{filename}")
def preview_report(filename: str, request: Request):
    """미리보기용 — 브라우저 인라인 표시, 다운로드 아님.

    HWPX/HWP는 바이너리 응답, TXT는 UTF-8 텍스트로 반환한다.
    프론트엔드의 rhwp 렌더러에서 fetch로 가져가 파싱한다.
    """
    try:
        filepath = _safe_report_path(filename)
    except HTTPException as e:
        return {"error": e.detail, "filename": filename}
    if not os.path.isfile(filepath):
        return {"error": "파일을 찾을 수 없습니다.", "filename": filename}
    if filename.endswith(".hwpx"):
        media_type = "application/hwp+zip"
    elif filename.endswith(".hwp"):
        media_type = "application/x-hwp"
    else:
        media_type = "text/plain; charset=utf-8"
    # inline 표시
    return FileResponse(filepath, media_type=media_type)


@router.post("/upload")
async def upload_report(file: UploadFile = File(...)):
    """사용자가 한컴오피스에서 수정한 보고서 파일을 업로드한다.

    - 허용 확장자: .hwpx, .hwp
    - 동일 파일명이 이미 존재하면 ' (편집)_타임스탬프'를 붙여 보존
    """
    raw_name = file.filename or ""
    if not raw_name:
        raise HTTPException(status_code=400, detail="파일명이 비어있습니다.")

    # 경로 우회 방지 — basename만 사용
    base = os.path.basename(raw_name)
    base = _UNSAFE_CHARS.sub("_", base)
    if not base or base in (".", ".."):
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명")

    if not base.lower().endswith(_ALLOWED_EXT):
        raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식 ({', '.join(_ALLOWED_EXT)}만 가능)")

    os.makedirs(REPORTS_DIR, exist_ok=True)

    # 동일 이름 충돌 시 편집본 표기
    name_part, ext_part = os.path.splitext(base)
    target_name = base
    target_path = os.path.join(REPORTS_DIR, target_name)
    if os.path.exists(target_path):
        ts = datetime.now().strftime("%H%M%S")
        target_name = f"{name_part} (편집)_{ts}{ext_part}"
        target_path = os.path.join(REPORTS_DIR, target_name)

    # 안전한 절대 경로 검증
    abs_reports = os.path.abspath(REPORTS_DIR)
    abs_target = os.path.abspath(target_path)
    if not abs_target.startswith(abs_reports + os.sep):
        raise HTTPException(status_code=400, detail="유효하지 않은 경로")

    # 청크 단위 저장 (메모리/크기 제한)
    written = 0
    try:
        with open(target_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_UPLOAD_SIZE:
                    out.close()
                    os.remove(target_path)
                    raise HTTPException(status_code=413, detail=f"파일이 너무 큽니다 (최대 {_MAX_UPLOAD_SIZE // (1024*1024)}MB)")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # 부분 저장 정리
        if os.path.exists(target_path):
            try: os.remove(target_path)
            except OSError: pass
        raise HTTPException(status_code=500, detail=f"업로드 저장 실패: {e}")

    return {"status": "ok", "filename": target_name, "size": written}


@router.delete("/delete/{filename}")
def delete_report(filename: str, request: Request):
    try:
        filepath = _safe_report_path(filename)
    except HTTPException as e:
        return {"error": e.detail, "filename": filename}
    if not os.path.isfile(filepath):
        return {"error": "파일을 찾을 수 없습니다.", "filename": filename}
    try:
        os.remove(filepath)
        return {"status": "deleted", "filename": filename}
    except OSError as e:
        return {"error": f"삭제 실패: {e}", "filename": filename}
