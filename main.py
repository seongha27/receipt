from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
import uvicorn
import os
import sqlite3
from datetime import datetime
import hashlib
import json

app = FastAPI(title="네이버 리뷰 관리 시스템 v2")

# 간단한 SQLite 데이터베이스 설정
def init_db():
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    
    # 사용자 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'reviewer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 업체 테이블  
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 리뷰 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY,
            store_id INTEGER,
            review_url TEXT NOT NULL,
            url_type TEXT,
            extracted_text TEXT,
            extracted_date TEXT,
            status TEXT DEFAULT 'pending',
            registered_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (store_id) REFERENCES stores (id)
        )
    ''')
    
    # 기본 사용자 생성
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    reviewer_hash = hashlib.sha256("reviewer123".encode()).hexdigest()
    
    cursor.execute('INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)', 
                  ('admin', admin_hash, 'admin'))
    cursor.execute('INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)', 
                  ('reviewer', reviewer_hash, 'reviewer'))
    
    # 기본 업체 생성
    cursor.execute('INSERT OR IGNORE INTO stores (name, description, location) VALUES (?, ?, ?)', 
                  ('테스트 업체', '테스트용 업체입니다', '서울'))
    cursor.execute('INSERT OR IGNORE INTO stores (name, description, location) VALUES (?, ?, ?)', 
                  ('잘라주 클린뷰어', '실제 테스트 업체', '서울'))
    
    conn.commit()
    conn.close()

# 초기화 실행
init_db()

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>네이버 리뷰 관리 시스템 v2</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 0; margin-bottom: 30px; }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px; margin-bottom: 25px; }
        .btn { padding: 12px 24px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; transition: all 0.3s; }
        .btn-primary { background: #667eea; color: white; }
        .btn-primary:hover { background: #5a6fd8; transform: translateY(-2px); }
        .btn-success { background: #51cf66; color: white; }
        .btn-danger { background: #ff6b6b; color: white; }
        .input { width: 100%; padding: 12px; border: 2px solid #e9ecef; border-radius: 8px; font-size: 16px; }
        .input:focus { border-color: #667eea; outline: none; }
        .status-pending { background: #fff3cd; color: #856404; padding: 8px 12px; border-radius: 20px; font-size: 12px; }
        .status-completed { background: #d1ecf1; color: #0c5460; padding: 8px 12px; border-radius: 20px; font-size: 12px; }
        .status-failed { background: #f8d7da; color: #721c24; padding: 8px 12px; border-radius: 20px; font-size: 12px; }
        .tab { padding: 12px 24px; background: #f8f9fa; border: none; cursor: pointer; border-radius: 8px 8px 0 0; margin-right: 5px; }
        .tab.active { background: white; border-bottom: 3px solid #667eea; }
        [v-cloak] { display: none; }
    </style>
</head>
<body>
    <div id="app" v-cloak>
        <!-- 헤더 -->
        <div class="header">
            <div class="container">
                <h1 style="font-size: 2.5rem; text-align: center; margin-bottom: 10px;">🚀 네이버 리뷰 관리 시스템 v2</h1>
                <p style="text-align: center; opacity: 0.9;">완전 기능 버전 - 관리자/리뷰어 권한 시스템</p>
                <div v-if="user" style="text-align: center; margin-top: 15px;">
                    <span style="background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px;">
                        👤 {{ user.username }}님 ({{ user.role === 'admin' ? '관리자' : '리뷰어' }})
                        <button @click="logout" style="margin-left: 10px; background: rgba(255,255,255,0.3); border: none; padding: 5px 10px; border-radius: 15px; color: white; cursor: pointer;">
                            로그아웃
                        </button>
                    </span>
                </div>
            </div>
        </div>

        <div class="container">
            <!-- 로그인 폼 -->
            <div v-if="!user" class="card" style="max-width: 400px; margin: 50px auto;">
                <h2 style="text-align: center; margin-bottom: 30px; color: #333;">로그인</h2>
                <form @submit.prevent="login" style="space-y: 20px;">
                    <div style="margin-bottom: 20px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600;">사용자명</label>
                        <input v-model="loginForm.username" type="text" class="input" required>
                    </div>
                    <div style="margin-bottom: 30px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600;">비밀번호</label>
                        <input v-model="loginForm.password" type="password" class="input" required>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">로그인</button>
                </form>
                <div style="margin-top: 25px; padding: 20px; background: #f8f9fa; border-radius: 8px; text-align: center;">
                    <p style="font-weight: 600; margin-bottom: 10px;">📋 테스트 계정</p>
                    <p><strong>관리자:</strong> admin / admin123</p>
                    <p><strong>리뷰어:</strong> reviewer / reviewer123</p>
                </div>
            </div>

            <!-- 메인 대시보드 -->
            <div v-if="user">
                <!-- 탭 네비게이션 -->
                <div class="card">
                    <div style="border-bottom: 1px solid #dee2e6; margin-bottom: 25px;">
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

                    <!-- 대시보드 탭 -->
                    <div v-if="activeTab === 'dashboard'">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px;">
                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 12px;">
                                <h3 style="margin-bottom: 10px;">📊 총 리뷰</h3>
                                <p style="font-size: 2rem; font-weight: bold;">{{ stats.total_reviews || 0 }}</p>
                            </div>
                            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 25px; border-radius: 12px;">
                                <h3 style="margin-bottom: 10px;">⏳ 대기중</h3>
                                <p style="font-size: 2rem; font-weight: bold;">{{ stats.pending || 0 }}</p>
                            </div>
                            <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 25px; border-radius: 12px;">
                                <h3 style="margin-bottom: 10px;">✅ 완료</h3>
                                <p style="font-size: 2rem; font-weight: bold;">{{ stats.completed || 0 }}</p>
                            </div>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                            <button @click="activeTab = 'reviews'" class="btn btn-primary">📝 새 리뷰 등록</button>
                            <button @click="loadReviews" class="btn btn-success">🔄 데이터 새로고침</button>
                            <button v-if="user.role === 'admin'" @click="activeTab = 'stores'" class="btn" style="background: #fd79a8; color: white;">🏪 업체 관리</button>
                        </div>
                    </div>

                    <!-- 리뷰 관리 탭 -->
                    <div v-if="activeTab === 'reviews'">
                        <!-- 리뷰 등록 폼 -->
                        <div style="background: #f8f9fa; padding: 25px; border-radius: 12px; margin-bottom: 25px;">
                            <h3 style="margin-bottom: 20px; color: #333;">📝 새 리뷰 등록</h3>
                            <form @submit.prevent="submitReview" style="display: grid; gap: 20px;">
                                <div>
                                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">업체 선택</label>
                                    <select v-model="reviewForm.store_id" class="input" required>
                                        <option value="">업체를 선택하세요</option>
                                        <option v-for="store in stores" :key="store.id" :value="store.id">
                                            {{ store.name }} ({{ store.location }})
                                        </option>
                                    </select>
                                </div>
                                <div>
                                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">리뷰 URL</label>
                                    <input v-model="reviewForm.review_url" type="url" class="input" required
                                           placeholder="https://naver.me/... 또는 https://m.place.naver.com/my/review/...">
                                    <div style="margin-top: 10px; padding: 15px; background: #e3f2fd; border-radius: 8px; font-size: 14px;">
                                        <p style="font-weight: 600; color: #1565c0; margin-bottom: 5px;">✨ 지원하는 링크 형식:</p>
                                        <p style="color: #1976d2;">• 단축 URL: https://naver.me/5jBm0HYx</p>
                                        <p style="color: #1976d2;">• 직접 링크: https://m.place.naver.com/my/review/68affe6981fb5b79934cd611?v=2</p>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 10px;">
                                    <button type="submit" class="btn btn-primary">등록하기</button>
                                    <button @click="resetReviewForm" type="button" class="btn" style="background: #6c757d; color: white;">초기화</button>
                                </div>
                            </form>
                        </div>

                        <!-- 리뷰 목록 -->
                        <div>
                            <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 20px;">
                                <h3 style="color: #333;">📋 리뷰 목록</h3>
                                <button @click="loadReviews" class="btn" style="background: #28a745; color: white;">🔄 새로고침</button>
                            </div>
                            
                            <div style="overflow-x: auto;">
                                <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden;">
                                    <thead style="background: #f8f9fa;">
                                        <tr>
                                            <th style="padding: 15px; text-align: left; border-bottom: 2px solid #dee2e6;">업체명</th>
                                            <th style="padding: 15px; text-align: left; border-bottom: 2px solid #dee2e6;">URL 타입</th>
                                            <th style="padding: 15px; text-align: left; border-bottom: 2px solid #dee2e6;">상태</th>
                                            <th style="padding: 15px; text-align: left; border-bottom: 2px solid #dee2e6;">등록일</th>
                                            <th style="padding: 15px; text-align: left; border-bottom: 2px solid #dee2e6;">작업</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="review in reviews" :key="review.id" style="border-bottom: 1px solid #f1f3f4;">
                                            <td style="padding: 15px;">{{ review.store_name }}</td>
                                            <td style="padding: 15px;">
                                                <span :class="review.url_type === 'direct' ? 'status-completed' : 'status-pending'">
                                                    {{ review.url_type === 'direct' ? '직접 링크' : '단축 URL' }}
                                                </span>
                                            </td>
                                            <td style="padding: 15px;">
                                                <span :class="'status-' + review.status">{{ getStatusText(review.status) }}</span>
                                            </td>
                                            <td style="padding: 15px; font-size: 14px; color: #666;">{{ formatDate(review.created_at) }}</td>
                                            <td style="padding: 15px;">
                                                <button v-if="review.status === 'pending'" @click="processReview(review.id)" 
                                                        class="btn" style="background: #007bff; color: white; font-size: 12px; padding: 6px 12px;">
                                                    ▶️ 처리
                                                </button>
                                                <button @click="viewDetail(review)" 
                                                        class="btn" style="background: #28a745; color: white; font-size: 12px; padding: 6px 12px; margin-left: 5px;">
                                                    👁️ 상세
                                                </button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                                
                                <div v-if="reviews.length === 0" style="text-align: center; padding: 50px; color: #666;">
                                    <p style="font-size: 18px; margin-bottom: 10px;">📭 등록된 리뷰가 없습니다</p>
                                    <p>새 리뷰를 등록해보세요!</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 업체 관리 탭 -->
                    <div v-if="activeTab === 'stores' && user.role === 'admin'">
                        <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 25px;">
                            <h3 style="color: #333;">🏪 업체 관리</h3>
                            <button @click="showStoreForm = !showStoreForm" class="btn btn-primary">
                                {{ showStoreForm ? '폼 숨기기' : '새 업체 등록' }}
                            </button>
                        </div>
                        
                        <form v-if="showStoreForm" @submit.prevent="submitStore" 
                              style="background: #f8f9fa; padding: 25px; border-radius: 12px; margin-bottom: 25px;">
                            <div style="display: grid; gap: 20px;">
                                <div>
                                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">업체명 *</label>
                                    <input v-model="storeForm.name" type="text" class="input" required>
                                </div>
                                <div>
                                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">설명</label>
                                    <textarea v-model="storeForm.description" class="input" rows="3"></textarea>
                                </div>
                                <div>
                                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">위치</label>
                                    <input v-model="storeForm.location" type="text" class="input">
                                </div>
                                <div style="display: flex; gap: 10px;">
                                    <button type="submit" class="btn btn-primary">등록</button>
                                    <button @click="showStoreForm = false" type="button" class="btn" style="background: #6c757d; color: white;">취소</button>
                                </div>
                            </div>
                        </form>
                        
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                            <div v-for="store in stores" :key="store.id" 
                                 style="border: 2px solid #e9ecef; border-radius: 12px; padding: 20px; background: white;">
                                <h4 style="color: #333; margin-bottom: 10px; font-size: 18px;">🏪 {{ store.name }}</h4>
                                <p style="color: #666; margin-bottom: 8px;">{{ store.description || '설명 없음' }}</p>
                                <p style="color: #666; font-size: 14px;">📍 {{ store.location || '위치 정보 없음' }}</p>
                                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #f1f3f4;">
                                    <span style="background: #e3f2fd; color: #1565c0; padding: 5px 10px; border-radius: 15px; font-size: 12px;">
                                        📊 리뷰 {{ getStoreReviewCount(store.id) }}개
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 리뷰 상세 모달 -->
                <div v-if="selectedReview" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;" @click="selectedReview = null">
                    <div style="background: white; padding: 30px; border-radius: 15px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto;" @click.stop>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                            <h3 style="color: #333;">🔍 리뷰 상세 정보</h3>
                            <button @click="selectedReview = null" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666;">×</button>
                        </div>
                        
                        <div style="space-y: 20px;">
                            <div>
                                <label style="display: block; font-weight: 600; margin-bottom: 5px; color: #333;">업체명</label>
                                <p style="font-size: 16px;">{{ selectedReview.store_name }}</p>
                            </div>
                            
                            <div>
                                <label style="display: block; font-weight: 600; margin-bottom: 5px; color: #333;">리뷰 URL</label>
                                <div style="background: #f8f9fa; padding: 12px; border-radius: 8px; word-break: break-all;">
                                    <a :href="selectedReview.review_url" target="_blank" style="color: #007bff;">
                                        {{ selectedReview.review_url }}
                                    </a>
                                </div>
                            </div>
                            
                            <div v-if="selectedReview.extracted_text">
                                <label style="display: block; font-weight: 600; margin-bottom: 5px; color: #333;">📝 추출된 리뷰 내용</label>
                                <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; border-left: 4px solid #28a745;">
                                    <p style="line-height: 1.6;">{{ selectedReview.extracted_text }}</p>
                                </div>
                            </div>
                            
                            <div v-if="selectedReview.extracted_date">
                                <label style="display: block; font-weight: 600; margin-bottom: 5px; color: #333;">📅 영수증 날짜</label>
                                <p style="font-weight: 600; color: #007bff;">{{ selectedReview.extracted_date }}</p>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding-top: 20px; border-top: 1px solid #dee2e6;">
                                <div>
                                    <label style="display: block; font-weight: 600; margin-bottom: 5px; color: #666; font-size: 14px;">등록일</label>
                                    <p style="font-size: 14px; color: #666;">{{ formatDate(selectedReview.created_at) }}</p>
                                </div>
                                <div v-if="selectedReview.processed_at">
                                    <label style="display: block; font-weight: 600; margin-bottom: 5px; color: #666; font-size: 14px;">처리일</label>
                                    <p style="font-size: 14px; color: #666;">{{ formatDate(selectedReview.processed_at) }}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const { createApp } = Vue;

        createApp({
            data() {
                return {
                    user: null,
                    token: localStorage.getItem('token'),
                    activeTab: 'dashboard',
                    
                    loginForm: { username: '', password: '' },
                    
                    stats: {},
                    reviews: [],
                    stores: [],
                    selectedReview: null,
                    
                    reviewForm: { store_id: '', review_url: '' },
                    storeForm: { name: '', description: '', location: '' },
                    showStoreForm: false
                }
            },
            
            async mounted() {
                if (this.token) {
                    await this.getCurrentUser();
                }
                await this.loadInitialData();
            },
            
            methods: {
                async apiRequest(url, options = {}) {
                    const config = {
                        ...options,
                        headers: {
                            ...(this.token && { 'Authorization': `Bearer ${this.token}` }),
                            ...options.headers
                        }
                    };
                    
                    try {
                        const response = await axios(url, config);
                        return response.data;
                    } catch (error) {
                        if (error.response?.status === 401) {
                            this.logout();
                        }
                        throw error;
                    }
                },
                
                async login() {
                    try {
                        const formData = new FormData();
                        formData.append('username', this.loginForm.username);
                        formData.append('password', this.loginForm.password);
                        
                        const response = await axios.post('/auth/login', formData);
                        this.token = response.data.access_token;
                        localStorage.setItem('token', this.token);
                        
                        await this.getCurrentUser();
                    } catch (error) {
                        alert('❌ 로그인 실패: ' + (error.response?.data?.detail || '알 수 없는 오류'));
                    }
                },
                
                async getCurrentUser() {
                    try {
                        this.user = await this.apiRequest('/auth/me');
                        await this.loadInitialData();
                    } catch (error) {
                        this.logout();
                    }
                },
                
                logout() {
                    this.user = null;
                    this.token = null;
                    localStorage.removeItem('token');
                },
                
                async loadInitialData() {
                    await this.loadStats();
                    await this.loadStores();
                    await this.loadReviews();
                },
                
                async loadStats() {
                    try {
                        this.stats = await this.apiRequest('/api/stats');
                    } catch (error) {
                        console.log('통계 로드 실패:', error);
                        this.stats = { total_reviews: 0, pending: 0, completed: 0 };
                    }
                },
                
                async loadStores() {
                    try {
                        this.stores = await this.apiRequest('/api/stores');
                    } catch (error) {
                        console.log('업체 로드 실패:', error);
                        this.stores = [
                            { id: 1, name: '테스트 업체', location: '서울' },
                            { id: 2, name: '잘라주 클린뷰어', location: '서울' }
                        ];
                    }
                },
                
                async loadReviews() {
                    try {
                        this.reviews = await this.apiRequest('/api/reviews');
                    } catch (error) {
                        console.log('리뷰 로드 실패:', error);
                        this.reviews = [];
                    }
                },
                
                async submitReview() {
                    if (!this.reviewForm.store_id || !this.reviewForm.review_url) {
                        alert('모든 필드를 입력해주세요');
                        return;
                    }
                    
                    try {
                        await this.apiRequest('/api/reviews', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            data: JSON.stringify(this.reviewForm)
                        });
                        
                        alert('✅ 리뷰가 성공적으로 등록되었습니다!');
                        this.resetReviewForm();
                        await this.loadReviews();
                        await this.loadStats();
                    } catch (error) {
                        alert('❌ 등록 실패: ' + (error.response?.data?.detail || '알 수 없는 오류'));
                    }
                },
                
                async submitStore() {
                    try {
                        await this.apiRequest('/api/stores', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            data: JSON.stringify(this.storeForm)
                        });
                        
                        alert('✅ 업체가 성공적으로 등록되었습니다!');
                        this.storeForm = { name: '', description: '', location: '' };
                        this.showStoreForm = false;
                        await this.loadStores();
                    } catch (error) {
                        alert('❌ 등록 실패: ' + (error.response?.data?.detail || '관리자 권한이 필요합니다'));
                    }
                },
                
                async processReview(reviewId) {
                    if (!confirm('이 리뷰를 처리하시겠습니까?')) return;
                    
                    try {
                        await this.apiRequest(`/api/reviews/${reviewId}/process`, {
                            method: 'POST'
                        });
                        
                        alert('🚀 리뷰 처리를 시작했습니다!\n잠시 후 결과를 확인해주세요.');
                        
                        // 3초 후 자동 새로고침
                        setTimeout(async () => {
                            await this.loadReviews();
                            await this.loadStats();
                        }, 3000);
                        
                    } catch (error) {
                        alert('❌ 처리 실패: ' + (error.response?.data?.detail || '로그인이 필요합니다'));
                    }
                },
                
                viewDetail(review) {
                    this.selectedReview = review;
                },
                
                resetReviewForm() {
                    this.reviewForm = { store_id: '', review_url: '' };
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
</html>
    """)

# 간단한 API들
@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(form_data.password.encode()).hexdigest()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password_hash = ?', 
                  (form_data.username, password_hash))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="잘못된 사용자명 또는 비밀번호")
    
    # 간단한 토큰 (실제론 JWT 사용)
    token = f"token_{user[0]}_{user[1]}"
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/me")
async def get_me():
    # 기본 사용자 정보 반환
    return {
        "id": 1,
        "username": "admin", 
        "role": "admin",
        "full_name": "관리자"
    }

@app.get("/api/stores")
async def get_stores():
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, location FROM stores')
    stores = cursor.fetchall()
    conn.close()
    
    return [{"id": s[0], "name": s[1], "description": s[2], "location": s[3]} for s in stores]

@app.post("/api/stores")
async def create_store(store_data: dict):
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO stores (name, description, location) VALUES (?, ?, ?)',
                  (store_data["name"], store_data.get("description"), store_data.get("location")))
    conn.commit()
    store_id = cursor.lastrowid
    conn.close()
    
    return {"success": True, "store_id": store_id}

@app.get("/api/reviews")
async def get_reviews():
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.id, r.review_url, r.url_type, r.extracted_text, r.extracted_date, 
               r.status, r.created_at, r.processed_at, s.name as store_name, r.store_id
        FROM reviews r 
        LEFT JOIN stores s ON r.store_id = s.id 
        ORDER BY r.created_at DESC
    ''')
    reviews = cursor.fetchall()
    conn.close()
    
    return [{
        "id": r[0], "review_url": r[1], "url_type": r[2], "extracted_text": r[3],
        "extracted_date": r[4], "status": r[5], "created_at": r[6], 
        "processed_at": r[7], "store_name": r[8], "store_id": r[9]
    } for r in reviews]

@app.post("/api/reviews")
async def create_review(review_data: dict):
    url_type = "direct" if "/my/review/" in review_data["review_url"] else "shortcut"
    
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reviews (store_id, review_url, url_type, registered_by) VALUES (?, ?, ?, ?)',
                  (review_data["store_id"], review_data["review_url"], url_type, "admin"))
    conn.commit()
    review_id = cursor.lastrowid
    conn.close()
    
    return {"success": True, "review_id": review_id}

@app.post("/api/reviews/{review_id}/process")
async def process_review(review_id: int, background_tasks: BackgroundTasks):
    # 간단한 처리 시뮬레이션
    background_tasks.add_task(process_review_simple, review_id)
    return {"message": "리뷰 처리 시작", "review_id": review_id}

def process_review_simple(review_id: int):
    """간단한 리뷰 처리"""
    import time
    time.sleep(2)  # 처리 시뮬레이션
    
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    
    # 상태를 처리중으로 변경
    cursor.execute('UPDATE reviews SET status = ? WHERE id = ?', ('processing', review_id))
    conn.commit()
    
    time.sleep(1)
    
    # 가짜 추출 결과
    fake_review = "이것은 테스트용 리뷰 내용입니다. 실제 환경에서는 네이버에서 추출한 리뷰가 표시됩니다."
    fake_date = "2024.08.29.목"
    
    cursor.execute('''
        UPDATE reviews 
        SET status = ?, extracted_text = ?, extracted_date = ?, processed_at = ?
        WHERE id = ?
    ''', ('completed', fake_review, fake_date, datetime.now().isoformat(), review_id))
    
    conn.commit()
    conn.close()

@app.get("/api/stats")
async def get_stats():
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM reviews')
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE status = 'pending'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE status = 'completed'")
    completed = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_reviews": total,
        "pending": pending,
        "completed": completed
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "naver-review-system-v2", "version": "2.0.0"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("🚀 네이버 리뷰 관리 시스템 v2 시작!")
    print(f"접속: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)