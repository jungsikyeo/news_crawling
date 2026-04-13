"""
NewsDesk 런처
- FastAPI 백엔드를 데몬 스레드로 실행
- 서버 준비 완료 후 브라우저 자동 오픈
- 프로세스 종료 시 서버도 함께 종료 (데몬 스레드)
"""
import sys
import os

# PyInstaller 번들 여부에 따라 베이스 디렉토리 설정
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')

for p in (BACKEND_DIR, BASE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import time
import threading
import webbrowser
import urllib.request
import urllib.error

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _run_server():
    try:
        import uvicorn
        from main import app  # backend/main.py (BACKEND_DIR이 sys.path에 있음)
        uvicorn.run(app, host=HOST, port=PORT, log_level="error")
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"서버 오류: {e}")
        print(err_msg)
        # frozen 환경에서 stdout이 안 보일 수 있으므로 파일에도 기록
        try:
            if getattr(sys, 'frozen', False):
                _install_root = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
            else:
                _install_root = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(_install_root, "logs")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "error.log"), "w", encoding="utf-8") as f:
                f.write(err_msg)
        except Exception:
            pass


def _wait_for_server(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{URL}/api/crawl/status", timeout=1)
            return True
        except urllib.error.HTTPError:
            # 서버가 응답했지만 HTTP 에러 (예: 404/405) → 서버는 살아있음
            return True
        except Exception:
            time.sleep(0.3)
    return False


if __name__ == "__main__":
    print("NewsDesk 시작 중...")

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    print("서버 준비 대기 중...")
    if _wait_for_server():
        print(f"서버 준비 완료: {URL}")
        webbrowser.open(URL)
    else:
        print("서버 시작에 실패했습니다.")
        sys.exit(1)

    # 메인 스레드를 살려두어 데몬 스레드(서버)가 유지되도록 함
    # 창 닫기 / Ctrl+C 시 자동 종료
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("NewsDesk 종료 중...")
