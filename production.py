"""
프로덕션용 메인 파일 - adksetch.info 도메인용
main.py를 기반으로 한 최적화된 버전
"""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 기존 main.py의 모든 기능을 그대로 사용
from main import app

if __name__ == "__main__":
    # 프로덕션 환경 설정
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"🚀 네이버 리뷰 웹앱 시작")
    print(f"📍 서버 주소: {host}:{port}")
    print(f"🌐 도메인: https://adksetch.info")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,  # 프로덕션에서는 reload 비활성화
        workers=1,     # 단일 워커 (ChromeDriver 충돌 방지)
        log_level="info"
    )