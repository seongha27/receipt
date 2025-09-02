# 네이버 리뷰 웹앱 도메인 배포 스크립트
# adksetch.info 도메인용

Write-Host "=== 네이버 리뷰 웹앱 배포 시작 ===" -ForegroundColor Green

# 1. 필수 소프트웨어 설치 확인
Write-Host "1. 필수 소프트웨어 확인 중..." -ForegroundColor Yellow

# Python 설치 확인
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python 설치됨: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python이 설치되지 않음. https://python.org 에서 설치 필요" -ForegroundColor Red
    exit 1
}

# Chrome 설치 확인
$chromePath = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" -ErrorAction SilentlyContinue
if ($chromePath) {
    Write-Host "✅ Chrome 브라우저 설치됨" -ForegroundColor Green
} else {
    Write-Host "❌ Chrome 브라우저 설치 필요" -ForegroundColor Red
    exit 1
}

# 2. 프로젝트 디렉토리로 이동
Write-Host "`n2. 프로젝트 디렉토리 설정..." -ForegroundColor Yellow
Set-Location -Path $PSScriptRoot

# 3. 가상환경 생성 및 활성화
Write-Host "`n3. Python 가상환경 설정..." -ForegroundColor Yellow
if (!(Test-Path "venv")) {
    python -m venv venv
    Write-Host "✅ 가상환경 생성 완료" -ForegroundColor Green
}

# 가상환경 활성화
& ".\venv\Scripts\Activate.ps1"
Write-Host "✅ 가상환경 활성화 완료" -ForegroundColor Green

# 4. 패키지 설치
Write-Host "`n4. Python 패키지 설치..." -ForegroundColor Yellow
pip install -r requirements.txt
Write-Host "✅ 패키지 설치 완료" -ForegroundColor Green

# 5. ChromeDriver 자동 설치
Write-Host "`n5. ChromeDriver 설치..." -ForegroundColor Yellow
pip install webdriver-manager
Write-Host "✅ ChromeDriver 관리자 설치 완료" -ForegroundColor Green

# 6. 데이터베이스 초기화
Write-Host "`n6. 데이터베이스 초기화..." -ForegroundColor Yellow
if (Test-Path "naver_reviews.db") {
    Remove-Item "naver_reviews.db" -Force
}
Write-Host "✅ 데이터베이스 초기화 완료" -ForegroundColor Green

# 7. 로컬 서버 테스트
Write-Host "`n7. 로컬 서버 테스트..." -ForegroundColor Yellow
Write-Host "서버를 시작합니다. Ctrl+C로 중지할 수 있습니다." -ForegroundColor Cyan
Write-Host "브라우저에서 http://localhost:8000 으로 접속하세요" -ForegroundColor Cyan

# 서버 실행
python main.py