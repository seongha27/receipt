# 🚀 네이버 리뷰 관리 시스템

고객사별 업체 관리와 네이버 플레이스 리뷰 자동 추출을 지원하는 웹 애플리케이션입니다.

## ✨ 주요 기능

### 🔐 사용자 권한 시스템
- **관리자**: 모든 기능 접근, 사용자/업체 관리, 리뷰어 할당
- **리뷰어**: 할당된 업체의 리뷰 URL 등록 및 조회

### 📊 리뷰 관리
- 두 가지 링크 형식 지원:
  - `https://naver.me/5jBm0HYx` (단축 URL)
  - `https://m.place.naver.com/my/review/68affe6981fb5b79934cd611?v=2` (직접 링크)
- 자동 리뷰 본문 및 영수증 날짜 추출
- 실시간 처리 상태 모니터링

### 🏢 다중 테넌트 지원
- 고객사별 데이터 분리
- 업체별 리뷰어 할당
- 권한 기반 데이터 접근

## 🛠️ 기술 스택

- **백엔드**: FastAPI, SQLAlchemy, PostgreSQL/SQLite
- **프론트엔드**: Vue.js 3, Tailwind CSS
- **인증**: JWT (JSON Web Tokens)
- **리뷰 추출**: Selenium, BeautifulSoup

## 📦 설치 방법

### 1. 로컬 개발 환경

```bash
# 1. 저장소 클론
git clone <repository-url>
cd naver-review-webapp

# 2. Python 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 설정
cp .env.example .env
# .env 파일에서 필요한 설정 수정

# 5. 데이터베이스 초기화 및 서버 실행
python main.py
```

서버 실행 후 http://localhost:8000 접속

**기본 관리자 계정**: `admin` / `admin123`

### 2. Docker로 실행

```bash
# 이미지 빌드
docker build -t naver-review-webapp .

# 컨테이너 실행
docker run -p 8000:8000 naver-review-webapp
```

## 🌐 무료 배포 가이드

### Railway 배포 (추천)

1. **GitHub 저장소 생성**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo>
   git push -u origin main
   ```

2. **Railway 계정 생성**
   - https://railway.app 방문
   - GitHub 계정으로 로그인

3. **프로젝트 배포**
   - "New Project" 클릭
   - "Deploy from GitHub repo" 선택
   - 저장소 선택
   - 자동으로 배포 시작

4. **환경변수 설정**
   - Dashboard → Variables 탭
   - 다음 변수 추가:
     ```
     SECRET_KEY=your-secret-key-here
     DATABASE_URL=postgresql://... (자동 생성됨)
     ```

5. **PostgreSQL 데이터베이스 추가**
   - "New" → "Database" → "Add PostgreSQL"
   - 자동으로 DATABASE_URL 연결됨

### Render 배포

1. **Render 계정 생성**
   - https://render.com 방문
   - GitHub 계정으로 로그인

2. **웹 서비스 생성**
   - "New" → "Web Service"
   - GitHub 저장소 연결
   - 설정:
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `python main.py`

3. **PostgreSQL 데이터베이스 추가**
   - "New" → "PostgreSQL"
   - 데이터베이스 생성 후 URL 복사

4. **환경변수 설정**
   ```
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=<postgresql-url>
   ```

## 📱 사용 방법

### 관리자 워크플로우

1. **업체 등록**
   - "업체 관리" 탭에서 새 업체 추가
   - 업체명, 설명, 위치 정보 입력

2. **리뷰어 계정 생성**
   - "사용자 관리" 탭에서 리뷰어 계정 생성
   - 사용자명, 이메일, 비밀번호 설정

3. **업체별 리뷰어 할당**
   - 각 업체에 담당 리뷰어 배정
   - 권한 기반 접근 제어

### 리뷰어 워크플로우

1. **로그인**
   - 관리자가 생성한 계정으로 로그인
   - 할당된 업체만 조회 가능

2. **리뷰 URL 등록**
   - "리뷰 관리" 탭에서 새 리뷰 등록
   - 두 가지 URL 형식 모두 지원:
     ```
     https://naver.me/5jBm0HYx
     https://m.place.naver.com/my/review/68affe6981fb5b79934cd611?v=2
     ```

3. **자동 처리**
   - "처리" 버튼 클릭으로 개별 리뷰 추출
   - 관리자는 "모든 대기 리뷰 처리" 가능

### 추출 결과 확인

- **대시보드**: 전체 통계 및 상태 모니터링
- **리뷰 상세**: 추출된 본문, 영수증 날짜 확인
- **실시간 상태**: 대기 → 처리중 → 완료/실패

## 🔧 API 문서

서버 실행 후 다음 URL에서 API 문서 확인:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 주요 API 엔드포인트

```
POST /auth/login          # 로그인
GET  /auth/me             # 현재 사용자 정보
POST /reviews/            # 리뷰 등록
GET  /reviews/            # 리뷰 목록
POST /reviews/{id}/process # 리뷰 처리
POST /stores/             # 업체 등록
GET  /stores/             # 업체 목록
POST /users/              # 사용자 생성 (관리자만)
GET  /dashboard/stats     # 대시보드 통계
```

## 🏗️ 프로젝트 구조

```
naver-review-webapp/
├── main.py              # FastAPI 애플리케이션 메인
├── models.py            # 데이터베이스 모델
├── schemas.py           # Pydantic 스키마
├── auth.py              # 인증 및 권한 시스템
├── database.py          # 데이터베이스 설정
├── review_extractor.py  # 리뷰 추출 서비스
├── templates/
│   └── index.html       # Vue.js 프론트엔드
├── static/              # 정적 파일
├── requirements.txt     # Python 의존성
├── Dockerfile           # Docker 설정
├── railway.json         # Railway 배포 설정
├── render.yaml          # Render 배포 설정
└── .env.example         # 환경변수 템플릿
```

## 🚨 주의사항

### 리뷰 추출 제한사항
- 네이버의 봇 탐지 시스템으로 인한 일시적 차단 가능
- 과도한 요청 시 IP 제한 가능성
- 리뷰 페이지 구조 변경시 추출 로직 업데이트 필요

### 서버 배포시 고려사항
- Chrome/ChromeDriver 설치 필요
- 충분한 메모리 확보 (최소 1GB 권장)
- 네트워크 접근 권한 필요

## 🔒 보안 고려사항

- 프로덕션 환경에서 반드시 강력한 SECRET_KEY 사용
- HTTPS 연결 권장
- 정기적인 보안 업데이트
- 데이터베이스 백업 필수

## 📞 지원

문제 발생시 다음을 확인해주세요:

1. **로그 확인**: 서버 콘솔 또는 로그 파일
2. **네트워크 상태**: 네이버 플레이스 접근 가능 여부
3. **브라우저 호환성**: Chrome 기반 브라우저 권장
4. **의존성 설치**: requirements.txt의 모든 패키지 설치 확인

## 📄 라이선스

이 프로젝트는 교육 및 연구 목적으로만 사용해주세요. 상업적 사용시 네이버의 이용약관을 준수해야 합니다.

---

🎉 **축하합니다!** 이제 완전한 네이버 리뷰 관리 시스템을 사용할 수 있습니다.