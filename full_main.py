from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import timedelta, datetime
from typing import List, Optional
import os
import json
import logging
from passlib.context import CryptContext
from jose import JWTError, jwt

# 데이터베이스 설정
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./naver_review_system.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 로컬 임포트
from full_models import *
from full_review_extractor import extract_naver_review_full
from google_sheets_service import GoogleSheetsService, create_google_sheets_service

# FastAPI 앱 생성
app = FastAPI(
    title="네이버 리뷰 관리 시스템 - 완전 기능 버전",
    description="네이버 플레이스 리뷰 자동 추출 및 관리 시스템 (구글 시트 연동)",
    version="2.0.0"
)

# 정적 파일 및 템플릿
if not os.path.exists("static"):
    os.makedirs("static")
if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.mount("/static", StaticFiles(directory="static"), name="static")

# 인증 설정
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# 의존성: 데이터베이스 세션
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 시작시 데이터베이스 초기화
try:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    create_initial_data(db)
    db.close()
    print("🚀 네이버 리뷰 관리 시스템이 시작되었습니다!")
except Exception as e:
    print(f"⚠️ 데이터베이스 초기화 오류: {e}")

# 인증 헬퍼 함수들
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="인증 실패")
    except JWTError:
        raise HTTPException(status_code=401, detail="인증 실패")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")
    
    # 마지막 로그인 시간 업데이트
    user.last_login = datetime.utcnow()
    db.commit()
    return user

# 메인 페이지
@app.get("/", response_class=HTMLResponse)
async def root():
    with open("full_template.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# 인증 API
@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="잘못된 사용자명 또는 비밀번호")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "company_id": current_user.company_id,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }

# 업체 관리 API
@app.get("/api/stores")
async def list_stores(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == UserRole.ADMIN:
        stores = db.query(Store).filter(Store.company_id == current_user.company_id).all()
    else:
        # 리뷰어는 할당된 업체만
        stores = db.query(Store).join(StoreReviewerAssignment).filter(
            Store.company_id == current_user.company_id,
            StoreReviewerAssignment.reviewer_id == current_user.id,
            StoreReviewerAssignment.is_active == True
        ).all()
    
    return [{"id": s.id, "name": s.name, "description": s.description, "location": s.location} for s in stores]

@app.post("/api/stores")
async def create_store(
    store_data: dict, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    store = Store(
        company_id=current_user.company_id,
        name=store_data["name"],
        description=store_data.get("description"),
        location=store_data.get("location")
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return {"success": True, "store_id": store.id}

# 리뷰 관리 API
@app.get("/api/reviews")
async def list_reviews(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Review).filter(Review.company_id == current_user.company_id)
    
    if current_user.role != UserRole.ADMIN:
        query = query.filter(Review.registered_by_user_id == current_user.id)
    
    reviews = query.order_by(Review.created_at.desc()).limit(100).all()
    
    result = []
    for review in reviews:
        store = db.query(Store).filter(Store.id == review.store_id).first()
        result.append({
            "id": review.id,
            "store_name": store.name if store else "알 수 없음",
            "review_url": review.review_url,
            "url_type": review.url_type,
            "status": review.status.value,
            "extracted_review_text": review.extracted_review_text,
            "extracted_receipt_date": review.extracted_receipt_date,
            "created_at": review.created_at.isoformat(),
            "processed_at": review.processed_at.isoformat() if review.processed_at else None
        })
    
    return result

@app.post("/api/reviews")
async def create_review(
    review_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 권한 확인
    if current_user.role != UserRole.ADMIN:
        # 리뷰어는 할당된 업체만 가능
        assignment = db.query(StoreReviewerAssignment).filter(
            StoreReviewerAssignment.store_id == review_data["store_id"],
            StoreReviewerAssignment.reviewer_id == current_user.id,
            StoreReviewerAssignment.is_active == True
        ).first()
        if not assignment:
            raise HTTPException(status_code=403, detail="해당 업체에 대한 권한이 없습니다")
    
    url_type = "direct" if "/my/review/" in review_data["review_url"] else "shortcut"
    
    review = Review(
        company_id=current_user.company_id,
        store_id=review_data["store_id"],
        registered_by_user_id=current_user.id,
        review_url=review_data["review_url"],
        url_type=url_type
    )
    
    db.add(review)
    db.commit()
    db.refresh(review)
    return {"success": True, "review_id": review.id}

# 리뷰 처리 함수
def process_review_background(review_id: int):
    """백그라운드에서 리뷰 처리"""
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return
        
        # 상태 업데이트
        review.status = ReviewStatus.PROCESSING
        review.processing_attempts += 1
        db.commit()
        
        # 업체명 가져오기
        store = db.query(Store).filter(Store.id == review.store_id).first()
        expected_shop_name = store.name if store else None
        
        # 리뷰 추출 실행
        review_text, receipt_date = extract_naver_review_full(
            review.review_url, 
            expected_shop_name
        )
        
        # 결과 저장
        review.extracted_review_text = review_text
        review.extracted_receipt_date = receipt_date
        review.extracted_store_name = expected_shop_name
        
        if "오류" not in review_text and "찾을 수 없습니다" not in review_text:
            review.status = ReviewStatus.COMPLETED
            
            # 구글 시트 동기화
            try:
                company = db.query(Company).filter(Company.id == review.company_id).first()
                if company and company.google_sheet_id:
                    sheets_service = create_google_sheets_service(company.google_sheet_id)
                    if sheets_service:
                        sync_data = {
                            "store_name": expected_shop_name,
                            "review_url": review.review_url,
                            "extracted_review_text": review_text,
                            "extracted_receipt_date": receipt_date,
                            "status": "completed"
                        }
                        sheets_service.sync_review_to_sheet(sync_data)
                        review.synced_to_sheet = True
            except Exception as e:
                review.sheet_sync_error = str(e)
        else:
            review.status = ReviewStatus.FAILED
            review.error_message = review_text
        
        review.processed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        review.status = ReviewStatus.FAILED
        review.error_message = str(e)
        db.commit()
    finally:
        db.close()

@app.post("/api/reviews/{review_id}/process")
async def process_review(
    review_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.company_id == current_user.company_id
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
    
    background_tasks.add_task(process_review_background, review_id)
    return {"message": "리뷰 처리를 시작했습니다", "review_id": review_id}

# 구글 시트 연동 API
@app.post("/api/google-sheets/setup")
async def setup_google_sheets(
    config_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    try:
        # 구글 시트 연결 테스트
        sheets_service = create_google_sheets_service(config_data["sheet_id"])
        if not sheets_service:
            raise HTTPException(status_code=400, detail="구글 시트 연결 실패")
        
        # 회사 정보 업데이트
        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        company.google_sheet_id = config_data["sheet_id"]
        company.google_sheet_status = GoogleSheetStatus.CONNECTED
        
        # 구글 시트 설정 저장
        init_google_sheet_config(db, current_user.company_id, config_data["sheet_id"], "credentials.json")
        
        return {"success": True, "message": "구글 시트 연결 성공"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"구글 시트 설정 실패: {str(e)}")

@app.get("/api/google-sheets/sync")
async def sync_with_google_sheets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """구글 시트와 데이터 동기화"""
    try:
        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        if not company or not company.google_sheet_id:
            raise HTTPException(status_code=400, detail="구글 시트가 설정되지 않았습니다")
        
        sheets_service = create_google_sheets_service(company.google_sheet_id)
        if not sheets_service:
            raise HTTPException(status_code=400, detail="구글 시트 연결 실패")
        
        # 대기중인 리뷰들 가져오기
        pending_reviews = sheets_service.get_pending_reviews()
        
        # 데이터베이스에 추가
        for sheet_review in pending_reviews:
            # 기존에 있는지 확인
            existing = db.query(Review).filter(Review.review_url == sheet_review["review_url"]).first()
            if existing:
                continue
            
            # 업체 찾기 또는 생성
            store = db.query(Store).filter(
                Store.name == sheet_review["store_name"],
                Store.company_id == current_user.company_id
            ).first()
            
            if not store:
                store = Store(
                    company_id=current_user.company_id,
                    name=sheet_review["store_name"],
                    google_sheet_row=sheet_review["row"]
                )
                db.add(store)
                db.flush()
            
            # 리뷰 생성
            url_type = "direct" if "/my/review/" in sheet_review["review_url"] else "shortcut"
            review = Review(
                company_id=current_user.company_id,
                store_id=store.id,
                registered_by_user_id=current_user.id,
                review_url=sheet_review["review_url"],
                url_type=url_type,
                google_sheet_row=sheet_review["row"]
            )
            db.add(review)
        
        db.commit()
        return {"success": True, "message": f"{len(pending_reviews)}개 리뷰를 동기화했습니다"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"동기화 실패: {str(e)}")

# 대시보드 통계
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base_query = db.query(Review).filter(Review.company_id == current_user.company_id)
    
    if current_user.role != UserRole.ADMIN:
        base_query = base_query.filter(Review.registered_by_user_id == current_user.id)
    
    stats = {
        "total_reviews": base_query.count(),
        "pending_reviews": base_query.filter(Review.status == ReviewStatus.PENDING).count(),
        "completed_reviews": base_query.filter(Review.status == ReviewStatus.COMPLETED).count(),
        "failed_reviews": base_query.filter(Review.status == ReviewStatus.FAILED).count(),
        "total_stores": db.query(Store).filter(Store.company_id == current_user.company_id).count(),
        "total_users": db.query(User).filter(User.company_id == current_user.company_id).count() if current_user.role == UserRole.ADMIN else 1
    }
    
    return stats

# 사용자 관리 (관리자만)
@app.post("/api/users")
async def create_user(
    user_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    # 중복 확인
    existing = db.query(User).filter(
        (User.username == user_data["username"]) | (User.email == user_data["email"])
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명 또는 이메일입니다")
    
    hashed_password = get_password_hash(user_data["password"])
    user = User(
        company_id=current_user.company_id,
        username=user_data["username"],
        email=user_data["email"],
        full_name=user_data.get("full_name"),
        role=UserRole(user_data["role"]),
        hashed_password=hashed_password
    )
    
    db.add(user)
    db.commit()
    return {"success": True, "user_id": user.id}

@app.get("/api/users")
async def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    users = db.query(User).filter(User.company_id == current_user.company_id).all()
    return [{
        "id": u.id, 
        "username": u.username, 
        "email": u.email, 
        "full_name": u.full_name,
        "role": u.role.value,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat()
    } for u in users]

# 업체-리뷰어 할당
@app.post("/api/assignments")
async def assign_reviewer(
    assignment_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    assignment = StoreReviewerAssignment(
        store_id=assignment_data["store_id"],
        reviewer_id=assignment_data["reviewer_id"],
        assigned_by=current_user.id
    )
    
    db.add(assignment)
    db.commit()
    return {"success": True}

@app.get("/api/assignments")
async def list_assignments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    assignments = db.query(StoreReviewerAssignment).join(Store).join(User).filter(
        Store.company_id == current_user.company_id,
        StoreReviewerAssignment.is_active == True
    ).all()
    
    result = []
    for assignment in assignments:
        store = db.query(Store).filter(Store.id == assignment.store_id).first()
        reviewer = db.query(User).filter(User.id == assignment.reviewer_id).first()
        result.append({
            "id": assignment.id,
            "store_name": store.name if store else "알 수 없음",
            "reviewer_name": reviewer.full_name or reviewer.username if reviewer else "알 수 없음",
            "assigned_at": assignment.assigned_at.isoformat()
        })
    
    return result

# 구글 크레덴셜 업로드
@app.post("/api/google-sheets/upload-credentials")
async def upload_credentials(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    try:
        # 파일 저장
        file_path = f"uploads/credentials_{current_user.company_id}.json"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 회사 정보 업데이트
        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        company.credentials_file_path = file_path
        db.commit()
        
        return {"success": True, "message": "인증 파일이 업로드되었습니다"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일 업로드 실패: {str(e)}")

# 헬스체크
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "naver-review-system-full", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)