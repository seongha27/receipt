from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os

from database import get_db
from models import User, UserRole
from schemas import TokenData

# 설정
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 비밀번호 해싱
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """사용자명으로 사용자 조회"""
    return db.query(User).filter(
        User.username == username,
        User.is_active == True
    ).first()

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """사용자 인증"""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """현재 사용자 조회 (토큰 기반)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보를 확인할 수 없습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    
    # 마지막 로그인 시간 업데이트
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """활성 사용자 확인"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="비활성 사용자")
    return current_user

def require_admin(current_user: User = Depends(get_current_active_user)):
    """관리자 권한 확인"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    return current_user

def require_admin_or_owner(user_id: int):
    """관리자이거나 본인인지 확인하는 의존성 생성기"""
    def check_permission(current_user: User = Depends(get_current_active_user)):
        if current_user.role != UserRole.ADMIN and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="권한이 없습니다"
            )
        return current_user
    return check_permission

def check_store_access(store_id: int):
    """업체 접근 권한 확인하는 의존성 생성기"""
    def check_permission(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
        from models import Store, StoreReviewerAssignment
        
        # 관리자는 모든 업체에 접근 가능
        if current_user.role == UserRole.ADMIN:
            return current_user
        
        # 리뷰어는 할당된 업체만 접근 가능
        store = db.query(Store).filter(
            Store.id == store_id,
            Store.company_id == current_user.company_id
        ).first()
        
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="업체를 찾을 수 없습니다"
            )
        
        # 할당 여부 확인
        assignment = db.query(StoreReviewerAssignment).filter(
            StoreReviewerAssignment.store_id == store_id,
            StoreReviewerAssignment.reviewer_id == current_user.id,
            StoreReviewerAssignment.is_active == True
        ).first()
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 업체에 대한 권한이 없습니다"
            )
        
        return current_user
    return check_permission

def check_company_access(current_user: User = Depends(get_current_active_user)):
    """동일 회사 데이터만 접근 가능하도록 확인"""
    return current_user

class PermissionChecker:
    """권한 확인 헬퍼 클래스"""
    
    @staticmethod
    def can_manage_users(user: User) -> bool:
        """사용자 관리 권한"""
        return user.role == UserRole.ADMIN
    
    @staticmethod
    def can_manage_stores(user: User) -> bool:
        """업체 관리 권한"""
        return user.role == UserRole.ADMIN
    
    @staticmethod
    def can_manage_assignments(user: User) -> bool:
        """할당 관리 권한"""
        return user.role == UserRole.ADMIN
    
    @staticmethod
    def can_view_all_reviews(user: User) -> bool:
        """모든 리뷰 조회 권한"""
        return user.role == UserRole.ADMIN
    
    @staticmethod
    def can_access_store(user: User, store_id: int, db: Session) -> bool:
        """업체 접근 권한"""
        if user.role == UserRole.ADMIN:
            return True
        
        from models import StoreReviewerAssignment
        assignment = db.query(StoreReviewerAssignment).filter(
            StoreReviewerAssignment.store_id == store_id,
            StoreReviewerAssignment.reviewer_id == user.id,
            StoreReviewerAssignment.is_active == True
        ).first()
        
        return assignment is not None