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
    <title>테스트</title>
</head>
<body>
    <h1>버튼 클릭 테스트</h1>
    
    <button onclick="testClick1()" style="padding: 10px 20px; background: red; color: white; border: none; margin: 10px;">빨간 버튼</button>
    <button onclick="testClick2()" style="padding: 10px 20px; background: blue; color: white; border: none; margin: 10px;">파란 버튼</button>
    <button onclick="testClick3()" style="padding: 10px 20px; background: green; color: white; border: none; margin: 10px;">초록 버튼</button>
    
    <div id="result" style="margin-top: 20px; padding: 20px; background: #f0f0f0;"></div>

    <script>
        function testClick1() {
            document.getElementById('result').innerHTML = '빨간 버튼이 클릭되었습니다!';
            alert('빨간 버튼 작동!');
        }
        
        function testClick2() {
            document.getElementById('result').innerHTML = '파란 버튼이 클릭되었습니다!';
            alert('파란 버튼 작동!');
        }
        
        function testClick3() {
            document.getElementById('result').innerHTML = '초록 버튼이 클릭되었습니다!';
            alert('초록 버튼 작동!');
        }
    </script>
</body>
</html>""")

if __name__ == "__main__":
    print("버튼 테스트 서버 시작")
    uvicorn.run(app, host="0.0.0.0", port=8000)