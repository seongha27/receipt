from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 데이터베이스 URL (환경변수 또는 기본값)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./naver_review_system.db"
)

# PostgreSQL을 위한 URL 수정 (Render, Railway 등에서 사용)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# 세션 로컬 클래스
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스
Base = declarative_base()

# 의존성: 데이터베이스 세션 가져오기
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 데이터베이스 테이블 생성
def create_tables():
    from models import Base
    Base.metadata.create_all(bind=engine)
    print("데이터베이스 테이블 생성 완료!")

# 초기 데이터 설정
def init_db():
    from models import create_initial_data
    db = SessionLocal()
    try:
        create_initial_data(db)
    finally:
        db.close()