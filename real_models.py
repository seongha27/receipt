from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import os

Base = declarative_base()

class Company(Base):
    """고객사 테이블 - 각 고객사는 완전히 분리된 데이터를 가짐"""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)  # 화면에 표시될 이름
    contact_email = Column(String(100), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    subscription_plan = Column(String(50), default="basic")  # basic, premium, enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    stores = relationship("Store", back_populates="company", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="company", cascade="all, delete-orphan")

class User(Base):
    """사용자 테이블 - 고객사별 관리자/리뷰어"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    username = Column(String(50), nullable=False, index=True)  # 고객사 내에서만 유니크
    email = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False)  # 'admin' or 'reviewer'
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # 관계
    company = relationship("Company", back_populates="users")
    store_assignments = relationship("StoreReviewerAssignment", back_populates="reviewer")
    reviews = relationship("Review", back_populates="registered_by")

class Store(Base):
    """업체 테이블 - 각 고객사의 관리 업체들"""
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    naver_place_url = Column(String(500), nullable=True)
    contact_info = Column(Text, nullable=True)  # 연락처 정보
    category = Column(String(50), nullable=True)  # 업종 (카페, 음식점 등)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    company = relationship("Company", back_populates="stores")
    reviewer_assignments = relationship("StoreReviewerAssignment", back_populates="store")
    reviews = relationship("Review", back_populates="store")

class StoreReviewerAssignment(Base):
    """업체별 리뷰어 할당 테이블"""
    __tablename__ = "store_reviewer_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 할당한 관리자
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)  # 할당 메모
    
    # 관계
    store = relationship("Store", back_populates="reviewer_assignments")
    reviewer = relationship("User", back_populates="store_assignments", foreign_keys=[reviewer_id])

class Review(Base):
    """리뷰 테이블 - 모든 리뷰 데이터"""
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    registered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # URL 정보
    review_url = Column(String(1000), nullable=False)
    url_type = Column(String(50), nullable=True)  # 'shortcut' or 'direct'
    
    # 추출된 리뷰 데이터
    extracted_review_text = Column(Text, nullable=True)
    extracted_receipt_date = Column(String(50), nullable=True)
    extracted_store_name = Column(String(100), nullable=True)
    
    # 메타데이터
    reviewer_name = Column(String(100), nullable=True)  # 리뷰 작성자명 (추출된)
    rating = Column(Integer, nullable=True)  # 별점 (추출된)
    visit_date = Column(String(50), nullable=True)  # 방문일 (추출된)
    
    # 상태 관리
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    processing_attempts = Column(Integer, default=0)
    
    # 시간 정보
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계
    company = relationship("Company", back_populates="reviews")
    store = relationship("Store", back_populates="reviews")
    registered_by = relationship("User", back_populates="reviews")

class ReviewExport(Base):
    """리뷰 데이터 내보내기 기록"""
    __tablename__ = "review_exports"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    exported_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    export_type = Column(String(20), nullable=False)  # 'excel', 'csv', 'json'
    filter_conditions = Column(Text, nullable=True)  # JSON 형태의 필터 조건
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    record_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 데이터베이스 설정
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./naver_review_webapp.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)

def create_initial_data():
    """초기 테스트 데이터 생성"""
    db = SessionLocal()
    try:
        # 기존 데이터 확인
        if db.query(Company).first():
            return  # 이미 데이터가 있으면 스킵
        
        # 테스트 고객사들 생성
        companies = [
            Company(name="adsketch", display_name="애드스케치", contact_email="admin@adsketch.co.kr"),
            Company(name="studioview", display_name="스튜디오뷰", contact_email="admin@studioview.co.kr"),
            Company(name="jh_company", display_name="제이에이치", contact_email="admin@jh.co.kr"),
        ]
        
        for company in companies:
            db.add(company)
        
        db.commit()
        
        # 비밀번호 해싱을 위한 간단한 함수
        import hashlib
        def simple_hash(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        # 각 고객사별 관리자 및 테스트 데이터 생성
        for company in companies:
            # 관리자 계정
            admin = User(
                company_id=company.id,
                username="admin",
                email=f"admin@{company.name}.com",
                hashed_password=simple_hash("admin123"),
                full_name=f"{company.display_name} 관리자",
                role="admin"
            )
            db.add(admin)
            
            # 리뷰어 계정들
            reviewers = [
                User(
                    company_id=company.id,
                    username="reviewer1",
                    email=f"reviewer1@{company.name}.com", 
                    hashed_password=simple_hash("reviewer123"),
                    full_name=f"{company.display_name} 리뷰어1",
                    role="reviewer"
                ),
                User(
                    company_id=company.id,
                    username="reviewer2",
                    email=f"reviewer2@{company.name}.com",
                    hashed_password=simple_hash("reviewer123"),
                    full_name=f"{company.display_name} 리뷰어2", 
                    role="reviewer"
                )
            ]
            
            for reviewer in reviewers:
                db.add(reviewer)
            
            # 테스트 업체들
            test_stores = [
                Store(
                    company_id=company.id,
                    name=f"{company.display_name} 카페",
                    description="테스트용 카페 업체",
                    location="서울특별시 강남구",
                    category="카페"
                ),
                Store(
                    company_id=company.id,
                    name=f"{company.display_name} 음식점", 
                    description="테스트용 음식점 업체",
                    location="서울특별시 서초구",
                    category="음식점"
                ),
                Store(
                    company_id=company.id,
                    name="잘라주 클린뷰어",
                    description="실제 테스트용 업체",
                    location="서울",
                    category="서비스업"
                )
            ]
            
            for store in test_stores:
                db.add(store)
        
        db.commit()
        
        # 업체별 리뷰어 할당
        for company in companies:
            company_stores = db.query(Store).filter(Store.company_id == company.id).all()
            company_reviewers = db.query(User).filter(
                User.company_id == company.id, 
                User.role == "reviewer"
            ).all()
            
            if company_stores and company_reviewers:
                # 첫 번째 리뷰어에게 첫 번째 업체 할당
                assignment = StoreReviewerAssignment(
                    store_id=company_stores[0].id,
                    reviewer_id=company_reviewers[0].id,
                    assigned_by=db.query(User).filter(
                        User.company_id == company.id,
                        User.role == "admin"
                    ).first().id
                )
                db.add(assignment)
        
        db.commit()
        print("✅ 초기 테스트 데이터 생성 완료!")
        print("\n📋 생성된 고객사별 계정:")
        
        for company in companies:
            print(f"\n🏢 {company.display_name} ({company.name}):")
            print(f"  👑 관리자: admin / admin123")
            print(f"  📝 리뷰어1: reviewer1 / reviewer123")
            print(f"  📝 리뷰어2: reviewer2 / reviewer123")
        
    except Exception as e:
        print(f"초기 데이터 생성 오류: {e}")
        db.rollback()
    finally:
        db.close()

def get_company_by_name(company_name: str):
    """고객사명으로 고객사 조회"""
    db = SessionLocal()
    try:
        return db.query(Company).filter(Company.name == company_name).first()
    finally:
        db.close()

def get_user_stores(user_id: int):
    """사용자가 접근 가능한 업체 목록"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        
        if user.role == "admin":
            # 관리자는 회사의 모든 업체 접근 가능
            return db.query(Store).filter(Store.company_id == user.company_id).all()
        else:
            # 리뷰어는 할당된 업체만 접근 가능
            return db.query(Store).join(StoreReviewerAssignment).filter(
                Store.company_id == user.company_id,
                StoreReviewerAssignment.reviewer_id == user.id,
                StoreReviewerAssignment.is_active == True
            ).all()
    finally:
        db.close()

def get_user_reviews(user_id: int, store_id: int = None):
    """사용자가 조회 가능한 리뷰 목록"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        
        query = db.query(Review).filter(Review.company_id == user.company_id)
        
        if user.role != "admin":
            # 리뷰어는 본인이 등록한 리뷰만 조회 가능
            query = query.filter(Review.registered_by_user_id == user.id)
        
        if store_id:
            query = query.filter(Review.store_id == store_id)
        
        return query.order_by(Review.created_at.desc()).all()
    finally:
        db.close()

def check_user_store_permission(user_id: int, store_id: int):
    """사용자의 특정 업체 접근 권한 확인"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store or store.company_id != user.company_id:
            return False
        
        if user.role == "admin":
            return True
        
        # 리뷰어는 할당된 업체만 접근 가능
        assignment = db.query(StoreReviewerAssignment).filter(
            StoreReviewerAssignment.store_id == store_id,
            StoreReviewerAssignment.reviewer_id == user.id,
            StoreReviewerAssignment.is_active == True
        ).first()
        
        return assignment is not None
    finally:
        db.close()