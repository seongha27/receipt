from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>테스트</title>
</head>
<body>
    <h1>네이버 리뷰 관리 시스템</h1>
    <p>서버가 정상 작동 중입니다!</p>
    <button onclick="alert('테스트 성공!')">클릭 테스트</button>
    
    <script>
        console.log('JavaScript 로드 완료');
        alert('페이지 로드 완료!');
    </script>
</body>
</html>""")

@app.get("/test")
async def test():
    return {"message": "API 테스트 성공"}

if __name__ == "__main__":
    print("디버그 서버 시작...")
    uvicorn.run(app, host="0.0.0.0", port=8002)