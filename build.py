"""
NewsDesk 빌드 스크립트
실행: python build.py

1. React 프론트엔드 빌드 (npm run build)
2. PyInstaller로 exe 생성 (launcher.py 기준)
"""
import subprocess
import sys
import os


ROOT = os.path.dirname(os.path.abspath(__file__))


def build_frontend():
    frontend_dir = os.path.join(ROOT, "frontend")
    print("=" * 40)
    print("[1/2] 프론트엔드 빌드 중...")
    subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend_dir,
        check=True,
        shell=(sys.platform == "win32"),
    )
    print("프론트엔드 빌드 완료")


def build_exe():
    sep = os.pathsep
    frontend_dist = os.path.join(ROOT, "frontend", "dist")
    assets_dir = os.path.join(ROOT, "assets")
    backend_dir = os.path.join(ROOT, "backend")
    launcher = os.path.join(ROOT, "server_entry.py")

    print("=" * 40)
    print("[2/2] exe 빌드 중...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "NewsDesk",
        "--onedir",
        "--paths", backend_dir,                               # 분석 시 backend/ 를 탐색 경로에 추가
        "--add-data", f"{frontend_dist}{sep}frontend/dist",  # React 빌드 결과물
        "--add-data", f"{assets_dir}{sep}assets",            # 포털 이미지 등
        "--add-data", f"{backend_dir}{sep}backend",          # 백엔드 Python 소스 (리소스)
        # uvicorn 필수 숨김 모듈
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        # 기타 의존성
        "--hidden-import", "apscheduler.schedulers.background",
        "--hidden-import", "apscheduler.triggers.interval",
        "--hidden-import", "lxml",
        "--hidden-import", "bs4",
        "--hidden-import", "requests",
        "--hidden-import", "main",          # backend/main.py
        "--hidden-import", "scheduler",     # backend/scheduler.py
        "--hidden-import", "db.database",   # backend/db/database.py
        "--hidden-import", "api.crawl",
        "--hidden-import", "api.news",
        "--hidden-import", "api.stats",
        "--hidden-import", "api.history",
        "--hidden-import", "crawlers.naver",
        "--hidden-import", "crawlers.daum",
        "--hidden-import", "crawlers.nate",
        # 전체 패키지 수집
        "--collect-all", "uvicorn",
        "--collect-all", "fastapi",
        "--collect-all", "starlette",
        "--noconfirm",
        "--clean",
        "--noconsole",
        launcher,
    ]

    subprocess.run(cmd, check=True)
    print("=" * 40)
    print("백엔드 빌드 완료!")
    print(f"  -> dist/NewsDesk/NewsDesk.exe")


def build_electron():
    electron_dir = os.path.join(ROOT, "electron")
    print("=" * 40)
    print("[3/3] Electron 빌드 중...")
    subprocess.run(
        ["npm", "install"],
        cwd=electron_dir,
        check=True,
        shell=(sys.platform == "win32"),
    )
    subprocess.run(
        ["npm", "run", "dist"],
        cwd=electron_dir,
        check=True,
        shell=(sys.platform == "win32"),
    )
    print("Electron 빌드 완료!")
    print(f"  -> dist-electron/")


if __name__ == "__main__":
    build_frontend()
    build_exe()
    build_electron()
