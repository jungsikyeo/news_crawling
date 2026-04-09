"""
PyInstaller 빌드 스크립트
실행: python build.py
"""
import subprocess
import sys
import os


def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(script_dir, "app.py")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "NewsCrawler",
        "--onedir",
        "--add-data", f"assets{os.pathsep}assets",
        "--hidden-import", "streamlit",
        "--hidden-import", "streamlit.runtime.scriptrunner",
        "--hidden-import", "streamlit.runtime.caching",
        "--hidden-import", "apscheduler",
        "--hidden-import", "apscheduler.schedulers.background",
        "--hidden-import", "apscheduler.triggers.interval",
        "--hidden-import", "plotly",
        "--hidden-import", "lxml",
        "--hidden-import", "bs4",
        "--collect-all", "streamlit",
        "--collect-all", "plotly",
        "--noconfirm",
        "--clean",
        app_path,
    ]

    print("빌드 시작...")
    subprocess.run(cmd, check=True)
    print("빌드 완료! dist/NewsCrawler 디렉토리를 확인하세요.")


if __name__ == "__main__":
    build()
