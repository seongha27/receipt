from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import os

app = FastAPI(title="네이버 리뷰 관리 시스템")

@app.get("/", response_class=HTMLResponse)
async def root():
    port = os.getenv("PORT", "8000")
    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>네이버 리뷰 관리 시스템</title>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                max-width: 600px; 
                margin: 100px auto; 
                padding: 20px;
                text-align: center;
            }}
            .success {{ 
                background: #10b981; 
                color: white; 
                padding: 20px; 
                border-radius: 10px;
                margin: 20px 0;
            }}
            .btn {{
                background: #2563eb;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                display: inline-block;
                margin: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>🚀 네이버 리뷰 관리 시스템</h1>
        
        <div class="success">
            ✅ 서버가 성공적으로 실행되었습니다!<br>
            포트: {port}
        </div>
        
        <h3>📊 주요 기능</h3>
        <ul style="text-align: left; display: inline-block;">
            <li>네이버 플레이스 리뷰 자동 추출</li>
            <li>관리자/리뷰어 권한 분리</li>
            <li>업체별 리뷰 관리</li>
            <li>실시간 처리 상태 모니터링</li>
        </ul>
        
        <div>
            <a href="/docs" class="btn">📚 API 문서</a>
            <a href="/health" class="btn">💚 서버 상태</a>
        </div>
    </body>
    </html>
    """

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "message": "서버가 정상 작동 중입니다!",
        "service": "naver-review-system"
    }

@app.get("/test")
async def test():
    return {"message": "테스트 성공!", "status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("서버 시작!")
    print(f"접속: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)