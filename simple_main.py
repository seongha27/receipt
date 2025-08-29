from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import os

# 간단한 FastAPI 앱
app = FastAPI(title="네이버 리뷰 관리 시스템 - 간단 버전")

# 메인 페이지
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>네이버 리뷰 관리 시스템</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #2563eb; text-align: center; }
            .success { 
                background: #10b981; 
                color: white; 
                padding: 15px; 
                border-radius: 5px;
                text-align: center;
                margin: 20px 0;
            }
            .feature {
                background: #f0f9ff;
                border-left: 4px solid #2563eb;
                padding: 15px;
                margin: 10px 0;
            }
            .btn {
                background: #2563eb;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                display: inline-block;
                margin: 10px 5px;
            }
            .btn:hover { background: #1d4ed8; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 네이버 리뷰 관리 시스템</h1>
            
            <div class="success">
                ✅ 서버가 성공적으로 실행되었습니다!
            </div>
            
            <div class="feature">
                <h3>📊 주요 기능</h3>
                <ul>
                    <li>네이버 플레이스 리뷰 자동 추출</li>
                    <li>관리자/리뷰어 권한 분리</li>
                    <li>업체별 리뷰 관리</li>
                    <li>실시간 처리 상태 모니터링</li>
                </ul>
            </div>
            
            <div class="feature">
                <h3>🔗 지원하는 링크 형식</h3>
                <ul>
                    <li><code>https://naver.me/5jBm0HYx</code> (단축 URL)</li>
                    <li><code>https://m.place.naver.com/my/review/...</code> (직접 링크)</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="/docs" class="btn">📚 API 문서 보기</a>
                <a href="/health" class="btn">💚 서버 상태 확인</a>
            </div>
            
            <div style="text-align: center; margin-top: 20px; color: #666;">
                <p>로컬에서 성공적으로 실행 중! 🎉</p>
                <p>포트: {}</p>
            </div>
        </div>
    </body>
    </html>
    """.format(os.getenv("PORT", 8000)))

# API 엔드포인트들
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "naver-review-system",
        "message": "서버가 정상 작동 중입니다!"
    }

@app.get("/api/test")
async def test_api():
    return {
        "success": True,
        "message": "API가 정상 작동합니다!",
        "features": [
            "네이버 리뷰 추출",
            "사용자 권한 관리",
            "업체별 리뷰 관리",
            "실시간 모니터링"
        ]
    }

# 리뷰 추출 테스트 (간단 버전)
@app.post("/api/extract-review")
async def extract_review_simple(data: dict):
    """간단한 리뷰 추출 테스트"""
    url = data.get("url", "")
    
    if not url:
        raise HTTPException(status_code=400, detail="URL이 필요합니다")
    
    # 간단한 응답
    return {
        "success": True,
        "url": url,
        "extracted_data": {
            "review_text": "테스트용 리뷰 내용입니다",
            "receipt_date": "2024.08.29",
            "shop_name": "테스트 업체"
        },
        "note": "현재는 테스트 모드입니다. 실제 추출 기능은 Chrome 설치 후 사용 가능합니다."
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("네이버 리뷰 관리 시스템이 시작됩니다!")
    print(f"접속 주소: http://localhost:{port}")
    print(f"API 문서: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)