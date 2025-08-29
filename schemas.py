from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Enums
class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"

class ReviewStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 기본 스키마들
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRoleEnum
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str
    company_id: int

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRoleEnum] = None

class User(UserBase):
    id: int
    company_id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

# 회사 스키마
class CompanyBase(BaseModel):
    name: str
    contact_email: Optional[EmailStr] = None

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# 업체 스키마
class StoreBase(BaseModel):
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    naver_place_url: Optional[str] = None

class StoreCreate(StoreBase):
    company_id: int

class StoreUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    naver_place_url: Optional[str] = None
    is_active: Optional[bool] = None

class Store(StoreBase):
    id: int
    company_id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# 리뷰 스키마
class ReviewBase(BaseModel):
    review_url: str
    store_id: int

class ReviewCreate(ReviewBase):
    pass

    @validator('review_url')
    def validate_review_url(cls, v):
        if not v or not v.strip():
            raise ValueError('리뷰 URL이 필요합니다')
        if not ('naver' in v.lower() and ('review' in v.lower() or 'naver.me' in v.lower())):
            raise ValueError('유효한 네이버 리뷰 URL이 아닙니다')
        return v.strip()

class ReviewUpdate(BaseModel):
    status: Optional[ReviewStatusEnum] = None
    extracted_review_text: Optional[str] = None
    extracted_receipt_date: Optional[str] = None
    error_message: Optional[str] = None

class Review(ReviewBase):
    id: int
    company_id: int
    registered_by_user_id: int
    url_type: Optional[str] = None
    extracted_review_text: Optional[str] = None
    extracted_receipt_date: Optional[str] = None
    extracted_store_name: Optional[str] = None
    status: ReviewStatusEnum
    error_message: Optional[str] = None
    processing_attempts: int
    created_at: datetime
    processed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# 업체-리뷰어 할당 스키마
class StoreReviewerAssignmentBase(BaseModel):
    store_id: int
    reviewer_id: int

class StoreReviewerAssignmentCreate(StoreReviewerAssignmentBase):
    pass

class StoreReviewerAssignment(StoreReviewerAssignmentBase):
    id: int
    assigned_at: datetime
    assigned_by: Optional[int] = None
    is_active: bool
    
    class Config:
        from_attributes = True

# 토큰 스키마
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# 대시보드 통계 스키마
class DashboardStats(BaseModel):
    total_reviews: int
    pending_reviews: int
    completed_reviews: int
    failed_reviews: int
    total_stores: int
    total_users: int
    recent_reviews: List[Review]

# API 응답 스키마
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class ReviewProcessResult(BaseModel):
    success: bool
    review_text: str
    receipt_date: str
    error_message: Optional[str] = None

# 리스트 응답 스키마
class UserList(BaseModel):
    users: List[User]
    total: int

class StoreList(BaseModel):
    stores: List[Store]
    total: int

class ReviewList(BaseModel):
    reviews: List[Review]
    total: int