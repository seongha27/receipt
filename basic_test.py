from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>기본 테스트</title>
</head>
<body>
    <h1>기본 HTML 테스트</h1>
    <p>이 텍스트가 보이나요?</p>
    <button onclick="alert('버튼 작동!')">클릭 테스트</button>
</body>
</html>""")

if __name__ == "__main__":
    print("기본 테스트 서버 시작")
    uvicorn.run(app, host="0.0.0.0", port=8000)