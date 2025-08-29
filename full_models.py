from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, Float
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

class GoogleSheetStatus(enum.Enum):
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    SYNC_FAILED = "sync_failed"

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact_email = Column(String(100), nullable=True)
    google_sheet_id = Column(String(200), nullable=True)  # 구글 시트 ID
    google_sheet_status = Column(Enum(GoogleSheetStatus), default=GoogleSheetStatus.NOT_CONNECTED)
    credentials_file_path = Column(String(500), nullable=True)  # 구글 인증 파일 경로
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

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

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    naver_place_url = Column(String(500), nullable=True)
    google_sheet_row = Column(Integer, nullable=True)  # 구글 시트의 행 번호
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class StoreReviewerAssignment(Base):
    __tablename__ = "store_reviewer_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)

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
    
    # 구글 시트 연동
    google_sheet_row = Column(Integer, nullable=True)  # 구글 시트 행 번호
    synced_to_sheet = Column(Boolean, default=False)
    sheet_sync_error = Column(Text, nullable=True)
    
    # 상태 관리
    status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING)
    error_message = Column(Text, nullable=True)
    processing_attempts = Column(Integer, default=0)
    
    # 시간 정보
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class GoogleSheetConfig(Base):
    __tablename__ = "google_sheet_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    sheet_id = Column(String(200), nullable=False)
    sheet_name = Column(String(100), default="영수증리뷰관리")
    
    # 컬럼 매핑 설정
    store_name_column = Column(String(5), default="A")  # A열: 업체명
    review_url_column = Column(String(5), default="B")  # B열: 리뷰URL  
    review_text_column = Column(String(5), default="C")  # C열: 리뷰본문
    receipt_date_column = Column(String(5), default="D")  # D열: 영수증날짜
    registration_date_column = Column(String(5), default="E")  # E열: 등록일
    status_column = Column(String(5), default="F")  # F열: 상태
    
    # 설정
    auto_sync_enabled = Column(Boolean, default=True)
    header_row = Column(Integer, default=1)  # 헤더가 있는 행
    data_start_row = Column(Integer, default=2)  # 데이터 시작 행
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

def create_initial_data(db_session):
    """초기 데이터 생성"""
    try:
        # 기본 회사 생성
        if not db_session.query(Company).first():
            default_company = Company(
                name="기본 회사",
                contact_email="admin@example.com"
            )
            db_session.add(default_company)
            db_session.flush()
            
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
            
            # 테스트 리뷰어 계정
            reviewer_user = User(
                company_id=default_company.id,
                username="reviewer",
                email="reviewer@example.com", 
                hashed_password=pwd_context.hash("reviewer123"),
                full_name="테스트 리뷰어",
                role=UserRole.REVIEWER
            )
            db_session.add(reviewer_user)
            
            # 테스트 업체들 생성
            test_stores = [
                Store(company_id=default_company.id, name="테스트 카페", description="테스트용 카페", location="서울 강남구"),
                Store(company_id=default_company.id, name="테스트 음식점", description="테스트용 음식점", location="서울 서초구"),
                Store(company_id=default_company.id, name="잘라주 클린뷰어", description="실제 테스트 업체", location="서울"),
            ]
            
            for store in test_stores:
                db_session.add(store)
            
            db_session.commit()
            
            # 리뷰어에게 첫 번째 업체 할당
            db_session.flush()
            assignment = StoreReviewerAssignment(
                store_id=test_stores[0].id,
                reviewer_id=reviewer_user.id,
                assigned_by=admin_user.id
            )
            db_session.add(assignment)
            db_session.commit()
            
            print("초기 데이터 생성 완료!")
            print("관리자 계정 - ID: admin, PW: admin123")
            print("리뷰어 계정 - ID: reviewer, PW: reviewer123")
            
    except Exception as e:
        print(f"초기 데이터 생성 오류: {e}")
        db_session.rollback()

# 구글 시트 연동을 위한 헬퍼 함수
def init_google_sheet_config(db_session, company_id, sheet_id, credentials_file):
    """구글 시트 설정 초기화"""
    try:
        config = GoogleSheetConfig(
            company_id=company_id,
            sheet_id=sheet_id
        )
        db_session.add(config)
        
        # 회사 정보 업데이트
        company = db_session.query(Company).filter(Company.id == company_id).first()
        if company:
            company.google_sheet_id = sheet_id
            company.credentials_file_path = credentials_file
            company.google_sheet_status = GoogleSheetStatus.CONNECTED
        
        db_session.commit()
        return True
    except Exception as e:
        print(f"구글 시트 설정 오류: {e}")
        db_session.rollback()
        return False