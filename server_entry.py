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
from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
