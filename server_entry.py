"""
Electron용 백엔드 서버 진입점
- 브라우저를 열지 않고 FastAPI 서버만 실행
- Electron이 프로세스를 관리함
"""
import sys
import os

BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')

for p in (BACKEND_DIR, BASE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
import time
from main import app

_HOST = "127.0.0.1"
_PORT = 8000


def _wait_for_port(host: str, port: int, timeout: int = 15) -> None:
    """포트가 사용 가능할 때까지 대기 (TIME_WAIT 해소)"""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            sock.close()
            return
        except OSError:
            sock.close()
            time.sleep(0.5)
    raise RuntimeError(f"Port {port} is not available after {timeout}s")


if __name__ == "__main__":
    try:
        _wait_for_port(_HOST, _PORT)
        uvicorn.run(app, host=_HOST, port=_PORT, log_level="error")
    except Exception:
        import traceback
        if getattr(sys, 'frozen', False):
            _install_root = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        else:
            _install_root = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(_install_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "error.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
