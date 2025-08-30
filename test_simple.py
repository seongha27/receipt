from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>테스트</title>
</head>
<body>
    <h1 style="text-align: center; margin-top: 100px; color: #333;">🚀 테스트 페이지</h1>
    <p style="text-align: center; margin-top: 20px;">서버가 정상 작동 중입니다!</p>
    <div style="text-align: center; margin-top: 30px;">
        <button onclick="alert('테스트 성공!')">클릭 테스트</button>
    </div>
</body>
</html>""")

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)