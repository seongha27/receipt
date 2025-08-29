from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"

class ReviewStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact_email = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # 관계
    users = relationship("User", back_populates="company")
    stores = relationship("Store", back_populates="company")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # 관계
    company = relationship("Company", back_populates="users")
    store_assignments = relationship("StoreReviewerAssignment", back_populates="reviewer")
    reviews = relationship("Review", back_populates="registered_by")

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    naver_place_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    company = relationship("Company", back_populates="stores")
    reviewer_assignments = relationship("StoreReviewerAssignment", back_populates="store")
    reviews = relationship("Review", back_populates="store")

class StoreReviewerAssignment(Base):
    __tablename__ = "store_reviewer_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # 관계
    store = relationship("Store", back_populates="reviewer_assignments")
    reviewer = relationship("User", back_populates="store_assignments", foreign_keys=[reviewer_id])

class Review(Base):
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
    
    # 상태 관리
    status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING)
    error_message = Column(Text, nullable=True)
    processing_attempts = Column(Integer, default=0)
    
    # 시간 정보
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계
    store = relationship("Store", back_populates="reviews")
    registered_by = relationship("User", back_populates="reviews")

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 데이터베이스 초기화 함수
def create_initial_data(db_session):
    """초기 데이터 생성"""
    
    # 기본 회사 생성
    if not db_session.query(Company).first():
        default_company = Company(
            name="기본 회사",
            contact_email="admin@example.com"
        )
        db_session.add(default_company)
        db_session.commit()
        
        # 기본 관리자 계정 생성 (비밀번호: admin123)
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        admin_user = User(
            company_id=default_company.id,
            username="admin",
            email="admin@example.com",
            hashed_password=pwd_context.hash("admin123"),
            full_name="시스템 관리자",
            role=UserRole.ADMIN
        )
        db_session.add(admin_user)
        db_session.commit()
        
        # 테스트 업체 생성
        test_store = Store(
            company_id=default_company.id,
            name="테스트 업체",
            description="테스트용 업체입니다",
            location="서울특별시"
        )
        db_session.add(test_store)
        db_session.commit()
        
        print("초기 데이터 생성 완료!")
        print("관리자 계정 - ID: admin, PW: admin123")