from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List, Optional
import os

# 로컬 임포트
from database import get_db, create_tables, init_db
from models import User, Store, Review, Company, StoreReviewerAssignment, UserRole, ReviewStatus
from schemas import *
from auth import *
from review_extractor import extract_naver_review

# FastAPI 앱 생성
app = FastAPI(
    title="네이버 리뷰 관리 시스템",
    description="네이버 플레이스 리뷰 자동 추출 및 관리 시스템",
    version="1.0.0"
)

# 정적 파일 서빙
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 시작시 데이터베이스 초기화
@app.on_event("startup")
async def startup_event():
    create_tables()
    init_db()
    print("🚀 네이버 리뷰 관리 시스템이 시작되었습니다!")

# 메인 페이지
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("templates/index.html" if os.path.exists("templates/index.html") else "static/index.html")

# 인증 라우터
@app.post("/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="잘못된 사용자명 또는 비밀번호",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

# 사용자 관리 API
@app.post("/users/", response_model=User)
async def create_user(
    user: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # 중복 확인
    db_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 사용자명 또는 이메일입니다"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        **user.dict(exclude={'password'}),
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/", response_model=List[User])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).filter(
        User.company_id == current_user.company_id
    ).offset(skip).limit(limit).all()
    return users

# 업체 관리 API
@app.post("/stores/", response_model=Store)
async def create_store(
    store: StoreCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    db_store = Store(**store.dict(), company_id=current_user.company_id)
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store

@app.get("/stores/", response_model=List[Store])
async def list_stores(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.role == UserRole.ADMIN:
        # 관리자는 모든 업체 조회 가능
        stores = db.query(Store).filter(
            Store.company_id == current_user.company_id
        ).offset(skip).limit(limit).all()
    else:
        # 리뷰어는 할당된 업체만 조회 가능
        stores = db.query(Store).join(StoreReviewerAssignment).filter(
            Store.company_id == current_user.company_id,
            StoreReviewerAssignment.reviewer_id == current_user.id,
            StoreReviewerAssignment.is_active == True
        ).offset(skip).limit(limit).all()
    return stores

# 업체-리뷰어 할당 API
@app.post("/assignments/", response_model=StoreReviewerAssignment)
async def assign_reviewer_to_store(
    assignment: StoreReviewerAssignmentCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # 중복 할당 확인
    existing = db.query(StoreReviewerAssignment).filter(
        StoreReviewerAssignment.store_id == assignment.store_id,
        StoreReviewerAssignment.reviewer_id == assignment.reviewer_id,
        StoreReviewerAssignment.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="이미 할당된 리뷰어입니다"
        )
    
    db_assignment = StoreReviewerAssignment(
        **assignment.dict(),
        assigned_by=current_user.id
    )
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    return db_assignment

@app.get("/assignments/", response_model=List[StoreReviewerAssignment])
async def list_assignments(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    assignments = db.query(StoreReviewerAssignment).join(Store).filter(
        Store.company_id == current_user.company_id,
        StoreReviewerAssignment.is_active == True
    ).all()
    return assignments

# 리뷰 관리 API
@app.post("/reviews/", response_model=Review)
async def create_review(
    review: ReviewCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # 업체 접근 권한 확인
    if current_user.role != UserRole.ADMIN:
        from auth import PermissionChecker
        if not PermissionChecker.can_access_store(current_user, review.store_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 업체에 대한 권한이 없습니다"
            )
    
    # URL 타입 결정
    url_type = "direct" if "/my/review/" in review.review_url else "shortcut"
    
    db_review = Review(
        **review.dict(),
        company_id=current_user.company_id,
        registered_by_user_id=current_user.id,
        url_type=url_type
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

@app.get("/reviews/", response_model=List[Review])
async def list_reviews(
    skip: int = 0,
    limit: int = 100,
    store_id: Optional[int] = None,
    status: Optional[ReviewStatusEnum] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Review).filter(Review.company_id == current_user.company_id)
    
    if current_user.role != UserRole.ADMIN:
        # 리뷰어는 본인이 등록한 리뷰만 조회
        query = query.filter(Review.registered_by_user_id == current_user.id)
    
    if store_id:
        query = query.filter(Review.store_id == store_id)
    if status:
        query = query.filter(Review.status == status.value)
    
    reviews = query.offset(skip).limit(limit).all()
    return reviews

# 리뷰 처리 함수 (백그라운드)
def process_review_background(review_id: int):
    """백그라운드에서 리뷰 처리"""
    from database import SessionLocal
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
        review_text, receipt_date = extract_naver_review(
            review.review_url, 
            expected_shop_name
        )
        
        # 결과 저장
        review.extracted_review_text = review_text
        review.extracted_receipt_date = receipt_date
        review.extracted_store_name = expected_shop_name
        
        if "오류" not in review_text and "찾을 수 없습니다" not in review_text:
            review.status = ReviewStatus.COMPLETED
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

@app.post("/reviews/{review_id}/process")
async def process_review(
    review_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """리뷰 처리 시작"""
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.company_id == current_user.company_id
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="리뷰를 찾을 수 없습니다")
    
    # 권한 확인
    if current_user.role != UserRole.ADMIN and review.registered_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="권한이 없습니다")
    
    # 백그라운드 작업 추가
    background_tasks.add_task(process_review_background, review_id)
    
    return {"message": "리뷰 처리를 시작했습니다", "review_id": review_id}

@app.post("/reviews/process-all")
async def process_all_pending_reviews(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """모든 대기중인 리뷰 처리"""
    pending_reviews = db.query(Review).filter(
        Review.company_id == current_user.company_id,
        Review.status == ReviewStatus.PENDING
    ).all()
    
    for review in pending_reviews:
        background_tasks.add_task(process_review_background, review.id)
    
    return {
        "message": f"{len(pending_reviews)}개의 리뷰 처리를 시작했습니다",
        "count": len(pending_reviews)
    }

# 대시보드 API
@app.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """대시보드 통계 데이터"""
    base_query = db.query(Review).filter(Review.company_id == current_user.company_id)
    
    if current_user.role != UserRole.ADMIN:
        base_query = base_query.filter(Review.registered_by_user_id == current_user.id)
    
    stats = {
        "total_reviews": base_query.count(),
        "pending_reviews": base_query.filter(Review.status == ReviewStatus.PENDING).count(),
        "completed_reviews": base_query.filter(Review.status == ReviewStatus.COMPLETED).count(),
        "failed_reviews": base_query.filter(Review.status == ReviewStatus.FAILED).count(),
        "total_stores": db.query(Store).filter(Store.company_id == current_user.company_id).count(),
        "total_users": db.query(User).filter(User.company_id == current_user.company_id).count(),
        "recent_reviews": base_query.order_by(Review.created_at.desc()).limit(10).all()
    }
    
    return stats

# 헬스체크
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "naver-review-system"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)