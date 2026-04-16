import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from report.generator import REPORTS_DIR

router = APIRouter()


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


@router.get("/download/{filename}")
def download_report(filename: str, request: Request):
    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.isfile(filepath):
        return {"error": "파일을 찾을 수 없습니다.", "filename": filename}
    if filename.endswith(".hwp"):
        media_type = "application/x-hwp"
    else:
        media_type = "text/plain; charset=utf-8"
    return FileResponse(filepath, media_type=media_type, filename=filename)
