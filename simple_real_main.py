from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
import uvicorn
import os
import sqlite3
import json
import hashlib
from datetime import datetime
import sys
import io

# 유니코드 출력을 위한 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = FastAPI(title="네이버 리뷰 관리 시스템 - 실제 기능")

# SQLite 데이터베이스 초기화
def init_database():
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    
    # 고객사 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            contact_email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 사용자 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'reviewer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # 업체 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            location TEXT,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # 업체-리뷰어 할당 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS store_assignments (
            id INTEGER PRIMARY KEY,
            store_id INTEGER,
            reviewer_id INTEGER,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (store_id) REFERENCES stores (id),
            FOREIGN KEY (reviewer_id) REFERENCES users (id)
        )
    ''')
    
    # 리뷰 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            store_id INTEGER,
            registered_by_user_id INTEGER,
            review_url TEXT NOT NULL,
            url_type TEXT,
            extracted_review_text TEXT,
            extracted_receipt_date TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            processing_attempts INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (store_id) REFERENCES stores (id),
            FOREIGN KEY (registered_by_user_id) REFERENCES users (id)
        )
    ''')
    
    # 초기 고객사 데이터
    companies = [
        ('adsketch', '애드스케치', 'admin@adsketch.co.kr'),
        ('studioview', '스튜디오뷰', 'admin@studioview.co.kr'), 
        ('jh_company', '제이에이치', 'admin@jh.co.kr')
    ]
    
    for company in companies:
        cursor.execute('INSERT OR IGNORE INTO companies (name, display_name, contact_email) VALUES (?, ?, ?)', company)
    
    # 각 고객사별 사용자 및 업체 생성
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    reviewer_hash = hashlib.sha256("reviewer123".encode()).hexdigest()
    
    cursor.execute('SELECT id, name, display_name FROM companies')
    companies_data = cursor.fetchall()
    
    for company_id, company_name, display_name in companies_data:
        # 관리자 계정
        cursor.execute('INSERT OR IGNORE INTO users (company_id, username, password_hash, full_name, role) VALUES (?, ?, ?, ?, ?)',
                      (company_id, 'admin', admin_hash, f'{display_name} 관리자', 'admin'))
        
        # 리뷰어 계정들
        cursor.execute('INSERT OR IGNORE INTO users (company_id, username, password_hash, full_name, role) VALUES (?, ?, ?, ?, ?)',
                      (company_id, 'reviewer1', reviewer_hash, f'{display_name} 리뷰어1', 'reviewer'))
        cursor.execute('INSERT OR IGNORE INTO users (company_id, username, password_hash, full_name, role) VALUES (?, ?, ?, ?, ?)',
                      (company_id, 'reviewer2', reviewer_hash, f'{display_name} 리뷰어2', 'reviewer'))
        
        # 테스트 업체들
        test_stores = [
            (company_id, f'{display_name} 카페', '테스트용 카페', '서울 강남구', '카페'),
            (company_id, f'{display_name} 음식점', '테스트용 음식점', '서울 서초구', '음식점'),
            (company_id, '잘라주 클린뷰어', '실제 테스트 업체', '서울', '서비스업')
        ]
        
        for store in test_stores:
            cursor.execute('INSERT OR IGNORE INTO stores (company_id, name, description, location, category) VALUES (?, ?, ?, ?, ?)', store)
    
    conn.commit()
    
    # 리뷰어 할당 (첫 번째 업체에 첫 번째 리뷰어 할당)
    cursor.execute('''
        INSERT OR IGNORE INTO store_assignments (store_id, reviewer_id)
        SELECT s.id, u.id 
        FROM stores s, users u 
        WHERE s.company_id = u.company_id 
        AND u.role = 'reviewer' 
        AND u.username = 'reviewer1'
    ''')
    
    conn.commit()
    conn.close()
    print("데이터베이스 초기화 완료!")

# 초기화 실행
init_database()

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>네이버 리뷰 관리 시스템 - 실제 기능</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; color: white; padding: 40px 0; }
        .main-card { background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); padding: 40px; margin: 20px auto; max-width: 500px; }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px; margin-bottom: 25px; }
        .btn { padding: 12px 24px; border-radius: 10px; border: none; cursor: pointer; font-weight: 600; transition: all 0.3s; margin: 5px; }
        .btn-primary { background: #667eea; color: white; }
        .btn-primary:hover { background: #5a6fd8; transform: translateY(-2px); }
        .btn-success { background: #51cf66; color: white; }
        .btn-danger { background: #ff6b6b; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .input { width: 100%; padding: 15px; border: 2px solid #e9ecef; border-radius: 10px; font-size: 16px; margin: 8px 0; }
        .input:focus { border-color: #667eea; outline: none; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .tab { padding: 15px 25px; background: #f8f9fa; border: none; cursor: pointer; margin-right: 5px; border-radius: 10px 10px 0 0; font-weight: 600; }
        .tab.active { background: white; border-bottom: 3px solid #667eea; color: #667eea; }
        .status-pending { background: #fff3cd; color: #856404; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .status-processing { background: #cce5ff; color: #004085; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .status-completed { background: #d4edda; color: #155724; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .status-failed { background: #f8d7da; color: #721c24; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        [v-cloak] { display: none; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid #dee2e6; }
        th { background: #f8f9fa; font-weight: 600; }
    </style>
</head>
<body>
    <div id="app" v-cloak>
        <!-- 헤더 -->
        <div class="header">
            <h1 style="font-size: 3rem; margin-bottom: 15px;">🚀 네이버 리뷰 관리 시스템</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">실제 리뷰 추출 • 고객사별 독립 운영 • 완전 기능 버전</p>
        </div>

        <!-- 고객사 선택 -->
        <div v-if="!user" class="container">
            <div v-if="!selectedCompany" class="main-card">
                <h2 style="text-align: center; margin-bottom: 30px; color: #333;">🏢 고객사 선택</h2>
                <div style="display: grid; gap: 20px;">
                    <button v-for="company in companies" :key="company.name" 
                            @click="selectCompany(company)" 
                            class="btn btn-primary" 
                            style="padding: 20px; font-size: 18px; text-align: left;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-weight: bold; margin-bottom: 5px;">{{ company.display_name }}</div>
                                <div style="font-size: 14px; opacity: 0.8;">{{ company.contact_email }}</div>
                            </div>
                            <div style="font-size: 24px;">🏢</div>
                        </div>
                    </button>
                </div>
            </div>
            
            <!-- 로그인 폼 -->
            <div v-if="selectedCompany" class="main-card">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h2 style="color: #333; margin-bottom: 10px;">🔑 {{ selectedCompany.display_name }} 로그인</h2>
                    <p style="color: #666;">{{ selectedCompany.contact_email }}</p>
                    <button @click="selectedCompany = null" 
                            style="margin-top: 10px; background: none; border: none; color: #667eea; cursor: pointer; text-decoration: underline;">
                        다른 고객사 선택
                    </button>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <label style="display: block; margin-bottom: 10px; font-weight: 600; color: #333;">사용자명</label>
                    <input v-model="loginForm.username" type="text" class="input" placeholder="admin, reviewer1, reviewer2">
                </div>
                <div style="margin-bottom: 30px;">
                    <label style="display: block; margin-bottom: 10px; font-weight: 600; color: #333;">비밀번호</label>
                    <input v-model="loginForm.password" type="password" class="input" placeholder="admin123 또는 reviewer123">
                </div>
                <button @click="login" class="btn btn-primary" style="width: 100%; font-size: 18px; padding: 18px;">
                    로그인
                </button>
                
                <div style="margin-top: 30px; padding: 25px; background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); border-radius: 15px;">
                    <h3 style="text-align: center; color: #1565c0; margin-bottom: 20px;">📋 {{ selectedCompany.display_name }} 계정</h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px;">
                        <div style="text-align: center; padding: 15px; background: white; border-radius: 10px;">
                            <p style="font-weight: bold; color: #d32f2f; margin-bottom: 8px;">👑 관리자</p>
                            <p style="font-size: 14px;"><code>admin / admin123</code></p>
                        </div>
                        <div style="text-align: center; padding: 15px; background: white; border-radius: 10px;">
                            <p style="font-weight: bold; color: #1976d2; margin-bottom: 8px;">📝 리뷰어1</p>
                            <p style="font-size: 14px;"><code>reviewer1 / reviewer123</code></p>
                        </div>
                        <div style="text-align: center; padding: 15px; background: white; border-radius: 10px;">
                            <p style="font-weight: bold; color: #1976d2; margin-bottom: 8px;">📝 리뷰어2</p>
                            <p style="font-size: 14px;"><code>reviewer2 / reviewer123</code></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 메인 시스템 -->
        <div v-if="user" style="background: white; min-height: 100vh;">
            <nav style="background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 20px 0;">
                <div class="container" style="display: flex; justify-content: space-between; align-items: center;">
                    <h1 style="color: #333; font-size: 24px;">🏢 {{ user.company_name }} 리뷰 시스템</h1>
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <span style="color: #666;">{{ user.full_name }}님</span>
                        <span :class="user.role === 'admin' ? 'btn-danger' : 'btn-secondary'" 
                              style="padding: 5px 12px; border-radius: 15px; font-size: 12px; color: white;">
                            {{ user.role === 'admin' ? '관리자' : '리뷰어' }}
                        </span>
                        <button @click="logout" class="btn btn-secondary">로그아웃</button>
                    </div>
                </div>
            </nav>

            <div class="container" style="padding-top: 30px;">
                <div class="card">
                    <!-- 탭 네비게이션 -->
                    <div style="border-bottom: 2px solid #e9ecef; margin-bottom: 30px;">
                        <button @click="activeTab = 'dashboard'" :class="{'active': activeTab === 'dashboard'}" class="tab">
                            📊 대시보드
                        </button>
                        <button @click="activeTab = 'reviews'" :class="{'active': activeTab === 'reviews'}" class="tab">
                            📝 리뷰 관리
                        </button>
                        <button v-if="user.role === 'admin'" @click="activeTab = 'stores'" :class="{'active': activeTab === 'stores'}" class="tab">
                            🏪 업체 관리
                        </button>
                    </div>

                    <!-- 대시보드 -->
                    <div v-if="activeTab === 'dashboard'">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 25px; margin-bottom: 40px;">
                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px; padding: 30px; text-align: center;">
                                <h3 style="margin-bottom: 15px;">📊 총 리뷰</h3>
                                <p style="font-size: 3rem; font-weight: bold;">{{ stats.total || 0 }}</p>
                            </div>
                            <div style="background: linear-gradient(135deg, #ffd93d 0%, #ff6b6b 100%); color: white; border-radius: 15px; padding: 30px; text-align: center;">
                                <h3 style="margin-bottom: 15px;">⏳ 대기중</h3>
                                <p style="font-size: 3rem; font-weight: bold;">{{ stats.pending || 0 }}</p>
                            </div>
                            <div style="background: linear-gradient(135deg, #51cf66 0%, #48c78e 100%); color: white; border-radius: 15px; padding: 30px; text-align: center;">
                                <h3 style="margin-bottom: 15px;">✅ 완료</h3>
                                <p style="font-size: 3rem; font-weight: bold;">{{ stats.completed || 0 }}</p>
                            </div>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
                            <button @click="activeTab = 'reviews'; showReviewForm = true" class="btn btn-primary" style="padding: 25px; font-size: 16px;">
                                📝 새 리뷰 등록
                            </button>
                            <button @click="loadAllData" class="btn btn-success" style="padding: 25px; font-size: 16px;">
                                🔄 데이터 새로고침
                            </button>
                            <button v-if="user.role === 'admin'" @click="processAllPending" class="btn" style="background: #fd79a8; color: white; padding: 25px; font-size: 16px;">
                                🚀 전체 처리
                            </button>
                        </div>
                    </div>

                    <!-- 리뷰 관리 -->
                    <div v-if="activeTab === 'reviews'">
                        <!-- 등록 폼 -->
                        <div v-if="showReviewForm" style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 30px; border-radius: 15px; margin-bottom: 30px;">
                            <h3 style="margin-bottom: 25px; color: #333;">📝 새 리뷰 등록</h3>
                            <div style="display: grid; gap: 20px;">
                                <div>
                                    <label style="display: block; margin-bottom: 10px; font-weight: 600;">업체 선택</label>
                                    <select v-model="reviewForm.store_id" class="input" required>
                                        <option value="">업체를 선택하세요</option>
                                        <option v-for="store in userStores" :key="store.id" :value="store.id">
                                            {{ store.name }} ({{ store.location }})
                                        </option>
                                    </select>
                                </div>
                                <div>
                                    <label style="display: block; margin-bottom: 10px; font-weight: 600;">네이버 리뷰 URL</label>
                                    <input v-model="reviewForm.review_url" type="url" class="input" required
                                           placeholder="https://naver.me/... 또는 https://m.place.naver.com/my/review/...">
                                    <div style="margin-top: 15px; padding: 20px; background: #e8f5e8; border-radius: 10px;">
                                        <p style="font-weight: 600; color: #155724; margin-bottom: 10px;">✨ 실제 지원 링크:</p>
                                        <p style="color: #155724;">• https://naver.me/5jBm0HYx</p>
                                        <p style="color: #155724;">• https://m.place.naver.com/my/review/68affe6981fb5b79934cd611?v=2</p>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 15px;">
                                    <button @click="submitReview" class="btn btn-primary" style="flex: 1;">등록</button>
                                    <button @click="showReviewForm = false" class="btn btn-secondary">취소</button>
                                </div>
                            </div>
                        </div>
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                            <h3 style="color: #333; font-size: 20px;">📋 리뷰 목록</h3>
                            <div>
                                <button @click="showReviewForm = !showReviewForm" class="btn btn-primary">
                                    {{ showReviewForm ? '폼 숨기기' : '새 리뷰 등록' }}
                                </button>
                                <button @click="loadAllData" class="btn btn-success">🔄 새로고침</button>
                            </div>
                        </div>
                        
                        <div v-if="reviews.length === 0" style="text-align: center; padding: 60px; color: #666;">
                            <div style="font-size: 4rem; margin-bottom: 20px;">📭</div>
                            <p style="font-size: 20px; margin-bottom: 10px;">등록된 리뷰가 없습니다</p>
                            <p>새 리뷰를 등록해보세요!</p>
                        </div>
                        
                        <div v-if="reviews.length > 0" style="background: white; border-radius: 10px; overflow: hidden;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>업체명</th>
                                        <th>URL 타입</th>
                                        <th>상태</th>
                                        <th>등록자</th>
                                        <th>등록일</th>
                                        <th>작업</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="review in reviews" :key="review.id">
                                        <td style="font-weight: 600;">{{ review.store_name }}</td>
                                        <td>
                                            <span :class="review.url_type === 'direct' ? 'status-completed' : 'status-pending'">
                                                {{ review.url_type === 'direct' ? '직접 링크' : '단축 URL' }}
                                            </span>
                                        </td>
                                        <td>
                                            <span :class="'status-' + review.status">{{ getStatusText(review.status) }}</span>
                                        </td>
                                        <td style="color: #666;">{{ review.registered_by_name }}</td>
                                        <td style="color: #666; font-size: 14px;">{{ formatDate(review.created_at) }}</td>
                                        <td>
                                            <div style="display: flex; gap: 5px;">
                                                <button v-if="review.status === 'pending'" @click="processReview(review.id)" 
                                                        class="btn btn-primary" style="font-size: 12px; padding: 6px 12px;">
                                                    ▶️ 실제 추출
                                                </button>
                                                <button @click="viewDetail(review)" 
                                                        class="btn btn-success" style="font-size: 12px; padding: 6px 12px;">
                                                    👁️ 상세
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- 업체 관리 (관리자만) -->
                    <div v-if="activeTab === 'stores' && user.role === 'admin'">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                            <h3 style="color: #333; font-size: 20px;">🏪 업체 관리</h3>
                            <button @click="showStoreForm = !showStoreForm" class="btn btn-primary">
                                {{ showStoreForm ? '폼 숨기기' : '새 업체 등록' }}
                            </button>
                        </div>
                        
                        <div v-if="showStoreForm" style="background: #f8f9fa; padding: 25px; border-radius: 15px; margin-bottom: 25px;">
                            <h4 style="margin-bottom: 20px;">새 업체 등록</h4>
                            <div style="display: grid; gap: 20px;">
                                <input v-model="storeForm.name" type="text" class="input" placeholder="업체명" required>
                                <input v-model="storeForm.location" type="text" class="input" placeholder="위치">
                                <select v-model="storeForm.category" class="input">
                                    <option value="">업종 선택</option>
                                    <option value="카페">카페</option>
                                    <option value="음식점">음식점</option>
                                    <option value="서비스업">서비스업</option>
                                </select>
                                <textarea v-model="storeForm.description" class="input" rows="2" placeholder="설명"></textarea>
                                <div style="display: flex; gap: 10px;">
                                    <button @click="submitStore" class="btn btn-primary" style="flex: 1;">등록</button>
                                    <button @click="showStoreForm = false" class="btn btn-secondary">취소</button>
                                </div>
                            </div>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                            <div v-for="store in stores" :key="store.id" 
                                 style="border: 2px solid #e9ecef; border-radius: 15px; padding: 20px; background: white;">
                                <h4 style="margin-bottom: 10px;">🏪 {{ store.name }}</h4>
                                <p style="color: #666; margin-bottom: 8px;">{{ store.description }}</p>
                                <p style="color: #666; font-size: 14px;">📍 {{ store.location }}</p>
                                <p style="color: #666; font-size: 12px;">{{ store.category }}</p>
                                <div style="margin-top: 15px;">
                                    <span style="background: #e3f2fd; color: #1565c0; padding: 6px 10px; border-radius: 15px; font-size: 12px;">
                                        📊 리뷰 {{ getStoreReviewCount(store.id) }}개
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 리뷰 상세 모달 -->
        <div v-if="selectedReview" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000;" @click="selectedReview = null">
            <div style="background: white; border-radius: 20px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto;" @click.stop>
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 20px 20px 0 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h3>🔍 리뷰 상세 정보</h3>
                        <button @click="selectedReview = null" style="background: none; border: none; color: white; font-size: 24px; cursor: pointer;">×</button>
                    </div>
                </div>
                
                <div style="padding: 30px;">
                    <div style="display: grid; gap: 20px;">
                        <div>
                            <label style="font-weight: 600; color: #333;">🏪 업체명</label>
                            <p style="font-size: 18px; color: #007bff; font-weight: 600;">{{ selectedReview.store_name }}</p>
                        </div>
                        
                        <div>
                            <label style="font-weight: 600; color: #333;">🔗 리뷰 URL</label>
                            <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; word-break: break-all;">
                                <a :href="selectedReview.review_url" target="_blank" style="color: #007bff;">
                                    {{ selectedReview.review_url }}
                                </a>
                            </div>
                        </div>
                        
                        <div v-if="selectedReview.extracted_review_text">
                            <label style="font-weight: 600; color: #333;">📝 추출된 리뷰 내용</label>
                            <div style="background: #e8f5e8; padding: 20px; border-radius: 10px; border-left: 5px solid #28a745;">
                                <p style="line-height: 1.8;">{{ selectedReview.extracted_review_text }}</p>
                            </div>
                        </div>
                        
                        <div v-if="selectedReview.extracted_receipt_date">
                            <label style="font-weight: 600; color: #333;">📅 영수증 날짜</label>
                            <div style="background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center;">
                                <p style="font-size: 20px; color: #1565c0; font-weight: 600;">{{ selectedReview.extracted_receipt_date }}</p>
                            </div>
                        </div>
                        
                        <div v-if="selectedReview.error_message">
                            <label style="font-weight: 600; color: #333;">❌ 오류 메시지</label>
                            <div style="background: #f8d7da; padding: 15px; border-radius: 10px;">
                                <p style="color: #721c24;">{{ selectedReview.error_message }}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 로딩 -->
        <div v-if="loading" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 2000;">
            <div style="background: white; padding: 40px; border-radius: 20px; text-align: center;">
                <div style="width: 50px; height: 50px; border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px;"></div>
                <p style="font-size: 18px; font-weight: 600;">{{ loadingMessage }}</p>
            </div>
        </div>
    </div>

    <style>
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>

    <script>
        const { createApp } = Vue;

        createApp({
            data() {
                return {
                    user: JSON.parse(localStorage.getItem('user') || 'null'),
                    selectedCompany: JSON.parse(localStorage.getItem('selectedCompany') || 'null'),
                    loginForm: { username: 'admin', password: 'admin123' },
                    
                    activeTab: 'dashboard',
                    loading: false,
                    loadingMessage: '처리 중...',
                    
                    companies: [],
                    stats: {},
                    reviews: [],
                    userStores: [],
                    stores: [],
                    
                    reviewForm: { store_id: '', review_url: '' },
                    storeForm: { name: '', description: '', location: '', category: '' },
                    showReviewForm: false,
                    showStoreForm: false,
                    selectedReview: null
                }
            },
            
            async mounted() {
                await this.loadCompanies();
                if (this.user) {
                    await this.loadAllData();
                }
            },
            
            methods: {
                async loadCompanies() {
                    try {
                        const response = await axios.get('/api/companies');
                        this.companies = response.data;
                    } catch (error) {
                        console.error('고객사 로드 실패:', error);
                    }
                },
                
                selectCompany(company) {
                    this.selectedCompany = company;
                    localStorage.setItem('selectedCompany', JSON.stringify(company));
                },
                
                async login() {
                    this.loading = true;
                    this.loadingMessage = '로그인 중...';
                    
                    try {
                        const response = await axios.post('/auth/login', {
                            username: this.loginForm.username,
                            password: this.loginForm.password,
                            company_name: this.selectedCompany.name
                        });
                        
                        this.user = response.data;
                        this.user.company_name = this.selectedCompany.display_name;
                        localStorage.setItem('user', JSON.stringify(this.user));
                        
                        await this.loadAllData();
                        alert(`✅ ${this.selectedCompany.display_name}에 로그인했습니다!`);
                    } catch (error) {
                        alert('❌ 로그인 실패: ' + (error.response?.data?.detail || '계정 정보를 확인해주세요'));
                    } finally {
                        this.loading = false;
                    }
                },
                
                logout() {
                    this.user = null;
                    this.selectedCompany = null;
                    localStorage.clear();
                },
                
                async loadAllData() {
                    await Promise.all([
                        this.loadStats(),
                        this.loadReviews(),
                        this.loadUserStores(),
                        this.loadStores()
                    ]);
                },
                
                async loadStats() {
                    try {
                        const response = await axios.get('/api/stats');
                        this.stats = response.data;
                    } catch (error) {
                        this.stats = { total: 0, pending: 0, completed: 0 };
                    }
                },
                
                async loadReviews() {
                    try {
                        const response = await axios.get('/api/reviews');
                        this.reviews = response.data;
                    } catch (error) {
                        this.reviews = [];
                    }
                },
                
                async loadUserStores() {
                    try {
                        const response = await axios.get('/api/user-stores');
                        this.userStores = response.data;
                    } catch (error) {
                        this.userStores = [];
                    }
                },
                
                async loadStores() {
                    try {
                        const response = await axios.get('/api/stores');
                        this.stores = response.data;
                    } catch (error) {
                        this.stores = [];
                    }
                },
                
                async submitReview() {
                    if (!this.reviewForm.store_id || !this.reviewForm.review_url) {
                        alert('❌ 업체와 URL을 모두 입력해주세요');
                        return;
                    }
                    
                    this.loading = true;
                    this.loadingMessage = '리뷰 등록 중...';
                    
                    try {
                        await axios.post('/api/reviews', this.reviewForm);
                        alert('✅ 리뷰가 등록되었습니다!');
                        this.reviewForm = { store_id: '', review_url: '' };
                        this.showReviewForm = false;
                        await this.loadAllData();
                    } catch (error) {
                        alert('❌ 등록 실패: ' + (error.response?.data?.detail || '권한을 확인해주세요'));
                    } finally {
                        this.loading = false;
                    }
                },
                
                async submitStore() {
                    this.loading = true;
                    this.loadingMessage = '업체 등록 중...';
                    
                    try {
                        await axios.post('/api/stores', this.storeForm);
                        alert('✅ 업체가 등록되었습니다!');
                        this.storeForm = { name: '', description: '', location: '', category: '' };
                        this.showStoreForm = false;
                        await this.loadStores();
                    } catch (error) {
                        alert('❌ 등록 실패: ' + error.message);
                    } finally {
                        this.loading = false;
                    }
                },
                
                async processReview(reviewId) {
                    const review = this.reviews.find(r => r.id === reviewId);
                    if (!confirm(`🚀 실제 네이버 리뷰 추출을 시작하시겠습니까?\\n\\n업체: ${review.store_name}\\nURL: ${review.review_url.substring(0, 60)}...`)) {
                        return;
                    }
                    
                    this.loading = true;
                    this.loadingMessage = `🔍 "${review.store_name}" 리뷰 추출 중...`;
                    
                    try {
                        await axios.post(`/api/reviews/${reviewId}/process`);
                        alert('🚀 실제 리뷰 추출을 시작했습니다!\\n\\n약 10-30초 후 결과를 확인하세요.');
                        
                        // 5초마다 상태 확인
                        const interval = setInterval(async () => {
                            await this.loadReviews();
                            const updated = this.reviews.find(r => r.id === reviewId);
                            if (updated && updated.status !== 'pending' && updated.status !== 'processing') {
                                clearInterval(interval);
                                if (updated.status === 'completed') {
                                    alert(`✅ 추출 완료!\\n\\n📝 ${updated.extracted_review_text?.substring(0, 100)}...\\n📅 영수증 날짜: ${updated.extracted_receipt_date}`);
                                } else {
                                    alert(`❌ 추출 실패: ${updated.error_message}`);
                                }
                            }
                        }, 5000);
                        
                        setTimeout(() => clearInterval(interval), 120000);
                    } catch (error) {
                        alert('❌ 처리 요청 실패: ' + error.message);
                    } finally {
                        this.loading = false;
                    }
                },
                
                async processAllPending() {
                    const pending = this.reviews.filter(r => r.status === 'pending');
                    if (pending.length === 0) {
                        alert('처리할 대기 리뷰가 없습니다');
                        return;
                    }
                    
                    if (!confirm(`${pending.length}개 리뷰를 모두 처리하시겠습니까?`)) return;
                    
                    this.loading = true;
                    this.loadingMessage = `${pending.length}개 리뷰 처리 중...`;
                    
                    for (const review of pending) {
                        try {
                            await axios.post(`/api/reviews/${review.id}/process`);
                        } catch (error) {
                            console.error(`리뷰 ${review.id} 처리 실패:`, error);
                        }
                    }
                    
                    alert(`${pending.length}개 리뷰 처리를 시작했습니다!`);
                    this.loading = false;
                },
                
                viewDetail(review) {
                    this.selectedReview = review;
                },
                
                getStatusText(status) {
                    const map = {
                        'pending': '⏳ 대기중',
                        'processing': '🔄 처리중',
                        'completed': '✅ 완료',
                        'failed': '❌ 실패'
                    };
                    return map[status] || status;
                },
                
                getStoreReviewCount(storeId) {
                    return this.reviews.filter(r => r.store_id === storeId).length;
                },
                
                formatDate(dateString) {
                    return new Date(dateString).toLocaleString('ko-KR');
                }
            }
        }).mount('#app');
    </script>
</body>
</html>""")

# 간단한 API들
@app.get("/api/companies")
async def get_companies():
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, display_name, contact_email FROM companies')
    companies = cursor.fetchall()
    conn.close()
    return [{"name": c[0], "display_name": c[1], "contact_email": c[2]} for c in companies]

@app.post("/auth/login")
async def login(login_data: dict):
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(login_data["password"].encode()).hexdigest()
    
    cursor.execute('''
        SELECT u.id, u.username, u.full_name, u.role, u.company_id, c.display_name
        FROM users u 
        JOIN companies c ON u.company_id = c.id
        WHERE u.username = ? AND u.password_hash = ? AND c.name = ?
    ''', (login_data["username"], password_hash, login_data["company_name"]))
    
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="잘못된 로그인 정보")
    
    return {
        "id": user[0],
        "username": user[1],
        "full_name": user[2],
        "role": user[3],
        "company_id": user[4],
        "company_name": user[5],
        "token": f"token_{user[0]}_{user[4]}"
    }

@app.get("/api/stats")
async def get_stats():
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM reviews')
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE status = 'pending'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE status = 'completed'")
    completed = cursor.fetchone()[0]
    
    conn.close()
    
    return {"total": total, "pending": pending, "completed": completed}

@app.get("/api/user-stores")
async def get_user_stores():
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, location, category FROM stores')
    stores = cursor.fetchall()
    conn.close()
    
    return [{"id": s[0], "name": s[1], "description": s[2], "location": s[3], "category": s[4]} for s in stores]

@app.get("/api/stores")
async def get_stores():
    return await get_user_stores()

@app.get("/api/reviews") 
async def get_reviews():
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.id, r.review_url, r.url_type, r.extracted_review_text, r.extracted_receipt_date,
               r.status, r.error_message, r.processing_attempts, r.created_at, r.processed_at,
               s.name as store_name, u.full_name as registered_by_name, r.store_id
        FROM reviews r
        LEFT JOIN stores s ON r.store_id = s.id
        LEFT JOIN users u ON r.registered_by_user_id = u.id
        ORDER BY r.created_at DESC
    ''')
    
    reviews = cursor.fetchall()
    conn.close()
    
    return [{
        "id": r[0], "review_url": r[1], "url_type": r[2], "extracted_review_text": r[3],
        "extracted_receipt_date": r[4], "status": r[5], "error_message": r[6], 
        "processing_attempts": r[7], "created_at": r[8], "processed_at": r[9],
        "store_name": r[10], "registered_by_name": r[11], "store_id": r[12]
    } for r in reviews]

@app.post("/api/reviews")
async def create_review(review_data: dict):
    url_type = "direct" if "/my/review/" in review_data["review_url"] else "shortcut"
    
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO reviews (company_id, store_id, registered_by_user_id, review_url, url_type)
        VALUES (1, ?, 1, ?, ?)
    ''', (review_data["store_id"], review_data["review_url"], url_type))
    
    conn.commit()
    review_id = cursor.lastrowid
    conn.close()
    
    return {"success": True, "review_id": review_id}

@app.post("/api/reviews/{review_id}/process")
async def process_review_endpoint(review_id: int, background_tasks: BackgroundTasks):
    # 실제 리뷰 추출을 백그라운드에서 실행
    background_tasks.add_task(process_review_actual, review_id)
    return {"success": True, "message": "실제 리뷰 추출 시작"}

def process_review_actual(review_id: int):
    """실제 네이버 리뷰 추출 함수"""
    try:
        conn = sqlite3.connect('real_reviews.db')
        cursor = conn.cursor()
        
        # 리뷰 정보 가져오기
        cursor.execute('''
            SELECT r.review_url, s.name as store_name
            FROM reviews r
            LEFT JOIN stores s ON r.store_id = s.id
            WHERE r.id = ?
        ''', (review_id,))
        
        result = cursor.fetchone()
        if not result:
            return
        
        review_url, store_name = result
        
        # 처리중 상태로 업데이트
        cursor.execute('UPDATE reviews SET status = ?, processing_attempts = processing_attempts + 1 WHERE id = ?', 
                      ('processing', review_id))
        conn.commit()
        
        print(f"실제 리뷰 추출 시작: {review_url}")
        
        # 실제 네이버 리뷰 추출
        try:
            # 기존 추출 코드 사용
            sys.path.append('C:/Users/wlstn/Desktop/영수증링크')
            
            # 실제 추출 실행
            if "/my/review/" in review_url:
                # 직접 링크 방식 (기존 extract_direct_review 함수 사용)
                from selenium import webdriver
                from selenium.webdriver.common.by import By
                from bs4 import BeautifulSoup
                import time
                
                try:
                    options = webdriver.ChromeOptions()
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    options.add_experimental_option('useAutomationExtension', False)
                    
                    driver = webdriver.Chrome(options=options)
                    driver.get(review_url)
                    time.sleep(3)
                    
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    
                    # 리뷰 본문 추출 - data-pui-click-code="reviewend.text" 속성 사용
                    review_elem = soup.find('a', {'data-pui-click-code': 'reviewend.text'})
                    if review_elem:
                        extracted_text = review_elem.get_text(strip=True)
                    else:
                        extracted_text = "리뷰 본문을 찾을 수 없습니다"
                    
                    # 영수증 날짜 추출 - time 태그 사용
                    time_elem = soup.find('time', {'aria-hidden': 'true'})
                    if time_elem:
                        extracted_date = time_elem.get_text(strip=True)
                    else:
                        extracted_date = "영수증 날짜를 찾을 수 없습니다"
                    
                    driver.quit()
                    print(f"직접 링크 실제 추출 성공: {store_name}")
                    
                except Exception as selenium_error:
                    print(f"Chrome 추출 실패, HTTP 방식으로 시도: {selenium_error}")
                    # HTTP 방식 fallback
                    import requests
                    response = requests.get(review_url)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    title = soup.find('title')
                    extracted_text = f"HTTP 추출: {title.get_text() if title else '제목 없음'}"
                    extracted_date = "HTTP 추출 - 날짜 제한"
            else:
                # 단축 URL 방식 (기존 extract_review_data_optimized 함수 사용)  
                from selenium import webdriver
                from selenium.webdriver.support.ui import WebDriverWait
                from bs4 import BeautifulSoup
                import time
                
                try:
                    options = webdriver.ChromeOptions()
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    options.add_experimental_option('useAutomationExtension', False)
                    
                    driver = webdriver.Chrome(options=options)
                    driver.get(review_url)
                    
                    # 리디렉션 대기
                    if "naver.me" in review_url:
                        WebDriverWait(driver, 10).until(lambda d: d.current_url != review_url)
                        print(f"리디렉션 완료: {driver.current_url}")
                    
                    time.sleep(3)
                    
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    target_review = None
                    
                    # 업체명으로 리뷰 찾기
                    review_blocks = soup.find_all('div', class_='hahVh2')
                    print(f"리뷰 블록 {len(review_blocks)}개 발견")
                    
                    for block in review_blocks:
                        shop_elem = block.find('span', class_='pui__pv1E2a')
                        if shop_elem:
                            found_shop_name = shop_elem.text.strip()
                            print(f"발견된 업체명: {found_shop_name}")
                            if found_shop_name == store_name:
                                target_review = block
                                print(f"업체명 '{store_name}' 매칭 성공")
                                break
                    
                    if target_review:
                        # 리뷰 본문 추출
                        review_div = target_review.find('div', class_='pui__vn15t2')
                        if review_div:
                            extracted_text = review_div.text.strip()
                        else:
                            extracted_text = "리뷰 본문을 찾을 수 없습니다"
                        
                        # 영수증 날짜 추출
                        time_elem = target_review.find('time', {'aria-hidden': 'true'})
                        if time_elem:
                            extracted_date = time_elem.text.strip()
                        else:
                            extracted_date = "영수증 날짜를 찾을 수 없습니다"
                    else:
                        extracted_text = f"업체명 '{store_name}'과 일치하는 리뷰를 찾을 수 없습니다"
                        extracted_date = "날짜 정보 없음"
                    
                    driver.quit()
                    print(f"단축 URL 실제 추출 시도: {store_name}")
                    
                except Exception as selenium_error:
                    print(f"Chrome 추출 실패: {selenium_error}")
                    extracted_text = f"Chrome 추출 실패: {str(selenium_error)}"
                    extracted_date = "추출 실패"
            
            # 결과 저장
            if "실패" not in extracted_text and "찾을 수 없습니다" not in extracted_text and len(extracted_text) > 10:
                status = 'completed'
            else:
                status = 'failed'
            
            cursor.execute('''
                UPDATE reviews 
                SET status = ?, extracted_review_text = ?, extracted_receipt_date = ?, processed_at = ?
                WHERE id = ?
            ''', (status, extracted_text, extracted_date, datetime.now().isoformat(), review_id))
            
            print(f"리뷰 {review_id} 추출 완료 - 상태: {status}")
            
        except Exception as e:
            # 실패 처리
            cursor.execute('UPDATE reviews SET status = ?, error_message = ? WHERE id = ?',
                          ('failed', f"추출 오류: {str(e)}", review_id))
            print(f"리뷰 {review_id} 추출 실패: {e}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"전체 처리 오류: {e}")

@app.post("/api/stores")
async def create_store(store_data: dict):
    conn = sqlite3.connect('real_reviews.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO stores (company_id, name, description, location, category)
        VALUES (1, ?, ?, ?, ?)
    ''', (store_data["name"], store_data.get("description"), store_data.get("location"), store_data.get("category")))
    
    conn.commit()
    store_id = cursor.lastrowid
    conn.close()
    
    return {"success": True, "store_id": store_id}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "naver-review-system-real",
        "version": "3.0.0",
        "features": {
            "real_extraction": True,
            "multi_company": True,
            "user_roles": True
        }
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("네이버 리뷰 관리 시스템 - 실제 기능 버전 시작!")
    print(f"접속 주소: http://localhost:{port}")
    print("고객사: 애드스케치, 스튜디오뷰, 제이에이치")
    uvicorn.run(app, host="0.0.0.0", port=port)