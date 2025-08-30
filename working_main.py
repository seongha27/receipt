from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
import uvicorn
import os
import sqlite3
import hashlib
from datetime import datetime
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = FastAPI(title="네이버 리뷰 관리 시스템")

def init_database():
    # 기존 DB 파일들 정리
    for db_file in ['reviews.db', 'real_reviews.db', 'sheet_style_reviews.db', 'complete_system.db', 'simple_system.db', 'final_system.db']:
        if os.path.exists(db_file):
            os.remove(db_file)
    
    conn = sqlite3.connect('working_system.db')
    cursor = conn.cursor()
    
    # 관리자
    cursor.execute('CREATE TABLE admin (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)')
    
    # 고객사 
    cursor.execute('CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT UNIQUE, password_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    
    # 업체
    cursor.execute('''CREATE TABLE stores (
        id INTEGER PRIMARY KEY, company_id INTEGER, name TEXT, 
        start_date DATE, daily_count INTEGER DEFAULT 1, duration_days INTEGER DEFAULT 30,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies (id)
    )''')
    
    # 리뷰어
    cursor.execute('CREATE TABLE reviewers (id INTEGER PRIMARY KEY, name TEXT UNIQUE, password_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    
    # 배정
    cursor.execute('''CREATE TABLE assignments (
        id INTEGER PRIMARY KEY, reviewer_id INTEGER, store_id INTEGER,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reviewer_id) REFERENCES reviewers (id),
        FOREIGN KEY (store_id) REFERENCES stores (id)
    )''')
    
    # 리뷰
    cursor.execute('''CREATE TABLE reviews (
        id INTEGER PRIMARY KEY, store_id INTEGER, store_name TEXT, review_url TEXT,
        extracted_text TEXT, extracted_date TEXT, status TEXT DEFAULT 'pending',
        url_type TEXT, registered_by TEXT, registered_by_type TEXT,
        error_message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, processed_at TIMESTAMP,
        FOREIGN KEY (store_id) REFERENCES stores (id)
    )''')
    
    # 관리자 계정
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute('INSERT INTO admin (username, password_hash) VALUES (?, ?)', ('admin', admin_hash))
    
    conn.commit()
    conn.close()
    print("DB 생성 완료!")

init_database()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>네이버 리뷰 관리 시스템</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f7fa; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #007bff 0%, #6f42c1 100%); color: white; padding: 20px 0; text-align: center; margin-bottom: 20px; }
        .card { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }
        .btn { padding: 8px 16px; border-radius: 4px; border: none; cursor: pointer; font-weight: 600; margin: 3px; font-size: 12px; }
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-warning { background: #ffc107; color: #333; }
        .btn-secondary { background: #6c757d; color: white; }
        .input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin: 5px 0; font-size: 12px; }
        .table { width: 100%; border-collapse: collapse; font-size: 11px; }
        .table th { background: #f8f9fa; border: 1px solid #ddd; padding: 6px; font-weight: 600; text-align: center; }
        .table td { border: 1px solid #ddd; padding: 6px; }
        .status-pending { background: #fff3cd; color: #856404; padding: 2px 6px; border-radius: 8px; font-size: 9px; }
        .status-completed { background: #d4edda; color: #155724; padding: 2px 6px; border-radius: 8px; font-size: 9px; }
        .status-failed { background: #f8d7da; color: #721c24; padding: 2px 6px; border-radius: 8px; font-size: 9px; }
        .login-box { background: white; padding: 25px; border-radius: 10px; max-width: 350px; margin: 80px auto; box-shadow: 0 5px 20px rgba(0,0,0,0.2); }
        .tab { padding: 8px 16px; background: #f8f9fa; border: none; cursor: pointer; margin-right: 3px; border-radius: 4px 4px 0 0; font-size: 12px; }
        .tab.active { background: white; border-bottom: 2px solid #007bff; color: #007bff; font-weight: 600; }
        [v-cloak] { display: none; }
    </style>
</head>
<body>
    <div id="app" v-cloak>
        <!-- 로딩 표시 -->
        <div v-if="loading" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 9999;">
            <div style="background: white; padding: 20px; border-radius: 10px; text-align: center;">
                <div style="width: 30px; height: 30px; border: 3px solid #f3f3f3; border-top: 3px solid #007bff; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                <p>{{ loadingMessage }}</p>
            </div>
        </div>

        <!-- 로그인 화면 -->
        <div v-if="!user" style="background: linear-gradient(135deg, #007bff 0%, #6f42c1 100%); min-height: 100vh;">
            <div class="login-box">
                <h2 style="text-align: center; margin-bottom: 20px;">🔐 로그인</h2>
                
                <div style="display: flex; gap: 3px; margin-bottom: 15px;">
                    <button @click="loginType = 'admin'" :class="loginType === 'admin' ? 'btn-danger' : 'btn-secondary'" style="flex: 1;">관리자</button>
                    <button @click="loginType = 'company'" :class="loginType === 'company' ? 'btn-primary' : 'btn-secondary'" style="flex: 1;">고객사</button>
                    <button @click="loginType = 'reviewer'" :class="loginType === 'reviewer' ? 'btn-success' : 'btn-secondary'" style="flex: 1;">리뷰어</button>
                </div>
                
                <input v-model="loginForm.username" type="text" class="input" 
                       :placeholder="loginType === 'admin' ? 'admin' : loginType === 'company' ? '고객사명' : '리뷰어명'">
                <input v-model="loginForm.password" type="password" class="input" 
                       :placeholder="loginType === 'admin' ? 'admin123' : '비밀번호'">
                
                <button @click="login" class="btn btn-primary" style="width: 100%; padding: 10px; margin-top: 10px;">로그인</button>
                
                <div style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                    <p style="font-size: 11px; color: #666;">기본 관리자: admin / admin123</p>
                </div>
            </div>
        </div>

        <!-- 메인 화면 -->
        <div v-if="user">
            <div class="header">
                <h1 style="font-size: 1.8rem;">
                    {{ user.type === 'admin' ? '🔧 시스템 관리자' : user.type === 'company' ? '🏢 ' + user.username : '👤 ' + user.username }}
                </h1>
                <button @click="logout" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 6px 12px; border-radius: 12px; cursor: pointer; font-size: 12px;">
                    로그아웃
                </button>
            </div>

            <div class="container">
                <div class="card">
                    <!-- 관리자 -->
                    <div v-if="user.type === 'admin'">
                        <div style="margin-bottom: 15px;">
                            <button @click="tab = 'companies'" :class="tab === 'companies' ? 'tab active' : 'tab'">고객사</button>
                            <button @click="tab = 'stores'" :class="tab === 'stores' ? 'tab active' : 'tab'">업체</button>
                            <button @click="tab = 'reviewers'" :class="tab === 'reviewers' ? 'tab active' : 'tab'">리뷰어</button>
                            <button @click="tab = 'assignments'" :class="tab === 'assignments' ? 'tab active' : 'tab'">배정</button>
                            <button @click="tab = 'reviews'" :class="tab === 'reviews' ? 'tab active' : 'tab'">리뷰관리</button>
                        </div>

                        <!-- 고객사 관리 -->
                        <div v-if="tab === 'companies'">
                            <h3>🏢 고객사 관리</h3>
                            <div style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                                <input v-model="companyForm.name" placeholder="고객사명" class="input" style="width: 200px; margin-right: 10px;">
                                <input v-model="companyForm.password" type="password" placeholder="비밀번호" class="input" style="width: 200px; margin-right: 10px;">
                                <button @click="createCompany" class="btn btn-primary">생성</button>
                            </div>
                            <table class="table">
                                <thead><tr><th>고객사명</th><th>생성일</th><th>업체수</th><th>리뷰수</th></tr></thead>
                                <tbody>
                                    <tr v-for="company in companies" :key="company.id">
                                        <td style="font-weight: 600;">{{ company.name }}</td>
                                        <td>{{ formatDate(company.created_at) }}</td>
                                        <td>{{ getCompanyStoreCount(company.id) }}개</td>
                                        <td>{{ getCompanyReviewCount(company.id) }}개</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- 업체 관리 -->
                        <div v-if="tab === 'stores'">
                            <h3>🏪 업체 관리</h3>
                            <div style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                                <select v-model="storeForm.company_id" class="input" style="width: 150px; margin-right: 10px;">
                                    <option value="">고객사</option>
                                    <option v-for="company in companies" :key="company.id" :value="company.id">{{ company.name }}</option>
                                </select>
                                <input v-model="storeForm.name" placeholder="업체명" class="input" style="width: 150px; margin-right: 10px;">
                                <input v-model="storeForm.start_date" type="date" class="input" style="width: 130px; margin-right: 10px;">
                                <input v-model="storeForm.daily_count" type="number" placeholder="하루갯수" class="input" style="width: 80px; margin-right: 10px;">
                                <input v-model="storeForm.duration_days" type="number" placeholder="일수" class="input" style="width: 80px; margin-right: 10px;">
                                <button @click="createStore" class="btn btn-primary">등록</button>
                            </div>
                            <table class="table">
                                <thead><tr><th>업체명</th><th>고객사</th><th>시작일</th><th>종료일</th><th>목표</th><th>진행</th></tr></thead>
                                <tbody>
                                    <tr v-for="store in stores" :key="store.id">
                                        <td style="font-weight: 600;">{{ store.name }}</td>
                                        <td>{{ store.company_name }}</td>
                                        <td>{{ store.start_date || '-' }}</td>
                                        <td>{{ getEndDate(store.start_date, store.duration_days) }}</td>
                                        <td>{{ getTotalTargetCount(store.daily_count, store.duration_days) }}개</td>
                                        <td>{{ getStoreCompletedCount(store.name) }}/{{ getTotalTargetCount(store.daily_count, store.duration_days) }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- 리뷰어 관리 -->
                        <div v-if="tab === 'reviewers'">
                            <h3>👥 리뷰어 관리</h3>
                            <div style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                                <input v-model="reviewerForm.name" placeholder="리뷰어명" class="input" style="width: 150px; margin-right: 10px;">
                                <input v-model="reviewerForm.password" type="password" placeholder="비밀번호" class="input" style="width: 150px; margin-right: 10px;">
                                <button @click="createReviewer" class="btn btn-success">생성</button>
                            </div>
                            <table class="table">
                                <thead><tr><th>리뷰어명</th><th>배정업체</th><th>리뷰수</th><th>생성일</th></tr></thead>
                                <tbody>
                                    <tr v-for="reviewer in reviewers" :key="reviewer.id">
                                        <td style="font-weight: 600;">{{ reviewer.name }}</td>
                                        <td>{{ getReviewerStores(reviewer.id) }}</td>
                                        <td>{{ getReviewerReviewCount(reviewer.name) }}개</td>
                                        <td>{{ formatDate(reviewer.created_at) }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- 배정 관리 -->
                        <div v-if="tab === 'assignments'">
                            <h3>🔗 배정 관리</h3>
                            <div style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                                <select v-model="assignForm.reviewer_id" class="input" style="width: 150px; margin-right: 10px;">
                                    <option value="">리뷰어</option>
                                    <option v-for="reviewer in reviewers" :key="reviewer.id" :value="reviewer.id">{{ reviewer.name }}</option>
                                </select>
                                <select v-model="assignForm.store_id" class="input" style="width: 200px; margin-right: 10px;">
                                    <option value="">업체</option>
                                    <option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }} ({{ store.company_name }})</option>
                                </select>
                                <button @click="createAssignment" class="btn btn-warning">배정</button>
                            </div>
                            <table class="table">
                                <thead><tr><th>리뷰어</th><th>업체명</th><th>고객사</th><th>배정일</th><th>작업</th></tr></thead>
                                <tbody>
                                    <tr v-for="assignment in assignments" :key="assignment.id">
                                        <td>{{ assignment.reviewer_name }}</td>
                                        <td>{{ assignment.store_name }}</td>
                                        <td>{{ assignment.company_name }}</td>
                                        <td>{{ formatDate(assignment.assigned_at) }}</td>
                                        <td><button @click="deleteAssignment(assignment.id)" class="btn btn-danger" style="padding: 3px 6px;">삭제</button></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- 리뷰 관리 -->
                        <div v-if="tab === 'reviews'">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                                <h3>📝 리뷰 관리 (추출 권한)</h3>
                                <div>
                                    <button @click="showAdminReviewForm = !showAdminReviewForm" class="btn btn-primary">+ 리뷰 추가</button>
                                    <button @click="processAllPending" class="btn btn-success">🚀 전체 처리</button>
                                </div>
                            </div>

                            <!-- 관리자 리뷰 추가 -->
                            <div v-if="showAdminReviewForm" style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                                <select v-model="adminReviewForm.store_id" class="input" style="width: 200px; margin-right: 10px;">
                                    <option value="">업체 선택</option>
                                    <option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }} ({{ store.company_name }})</option>
                                </select>
                                <input v-model="adminReviewForm.url" type="url" placeholder="리뷰 URL" class="input" style="width: 300px; margin-right: 10px;">
                                <button @click="addAdminReview" class="btn btn-primary">등록</button>
                            </div>

                            <table class="table">
                                <thead><tr><th>업체명</th><th>URL</th><th>리뷰내용</th><th>날짜</th><th>상태</th><th>등록자</th><th>작업</th></tr></thead>
                                <tbody>
                                    <tr v-for="review in allReviews" :key="review.id">
                                        <td style="font-weight: 600;">{{ review.store_name }}</td>
                                        <td style="font-size: 9px;"><a :href="review.review_url" target="_blank">{{ review.review_url.substring(0, 20) }}...</a></td>
                                        <td style="font-size: 9px; max-width: 150px; overflow: hidden;">{{ review.extracted_text || '-' }}</td>
                                        <td>{{ review.extracted_date || '-' }}</td>
                                        <td><span :class="'status-' + review.status">{{ getStatusText(review.status) }}</span></td>
                                        <td>{{ review.registered_by }}</td>
                                        <td>
                                            <button v-if="review.status === 'pending'" @click="processReview(review.id)" class="btn btn-primary" style="padding: 2px 6px;">▶️</button>
                                            <button @click="viewReview(review)" class="btn btn-success" style="padding: 2px 6px;">👁️</button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- 고객사 -->
                    <div v-if="user.type === 'company'">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                            <h3>🏢 {{ user.username }} 리뷰 현황</h3>
                            <button @click="exportMyData" class="btn btn-success">📊 리포트 다운로드</button>
                        </div>
                        
                        <!-- 업체별 현황 -->
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-bottom: 20px;">
                            <div v-for="store in myStores" :key="store.id" style="background: #e8f5e8; padding: 15px; border-radius: 8px;">
                                <h4 style="margin-bottom: 8px;">{{ store.name }}</h4>
                                <div style="font-size: 11px; color: #666; margin-bottom: 8px;">
                                    {{ store.start_date }} ~ {{ getEndDate(store.start_date, store.duration_days) }}
                                </div>
                                <div style="font-size: 11px; color: #666; margin-bottom: 8px;">
                                    목표: {{ getTotalTargetCount(store.daily_count, store.duration_days) }}개 ({{ store.daily_count }}개/일 × {{ store.duration_days }}일)
                                </div>
                                <div style="font-size: 14px; font-weight: bold; color: #155724;">
                                    {{ getStoreCompletedCount(store.name) }}/{{ getTotalTargetCount(store.daily_count, store.duration_days) }} 
                                    ({{ getStoreTargetProgress(store.name, store.daily_count, store.duration_days) }}%)
                                </div>
                            </div>
                        </div>

                        <!-- 완료된 리뷰만 (고객사용) -->
                        <table class="table">
                            <thead><tr><th>업체명</th><th>리뷰URL</th><th>리뷰내용</th><th>영수증날짜</th></tr></thead>
                            <tbody>
                                <tr v-for="review in myReviews.filter(r => r.status === 'completed')" :key="review.id">
                                    <td style="font-weight: 600;">{{ review.store_name }}</td>
                                    <td style="font-size: 9px;"><a :href="review.review_url" target="_blank">{{ review.review_url.substring(0, 25) }}...</a></td>
                                    <td style="font-size: 10px;">{{ review.extracted_text || '-' }}</td>
                                    <td style="text-align: center; font-weight: 600;">{{ review.extracted_date || '-' }}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- 리뷰어 -->
                    <div v-if="user.type === 'reviewer'">
                        <h3>👤 {{ user.username }} - 리뷰 등록</h3>
                        
                        <!-- 배정된 업체들 -->
                        <div style="margin: 15px 0;">
                            <h4>🏪 담당 업체</h4>
                            <div v-if="myAssignedStores.length === 0" style="padding: 20px; text-align: center; color: #666;">
                                배정된 업체가 없습니다
                            </div>
                            <div v-else style="display: flex; gap: 10px; margin: 10px 0;">
                                <div v-for="store in myAssignedStores" :key="store.id" 
                                     style="background: #e3f2fd; padding: 10px; border-radius: 6px; display: flex; align-items: center; gap: 10px;">
                                    <span>{{ store.name }}</span>
                                    <button @click="addReviewForStore(store)" class="btn btn-primary" style="padding: 4px 8px;">+ 리뷰</button>
                                </div>
                            </div>
                        </div>

                        <!-- 리뷰 추가 폼 -->
                        <div v-if="showReviewerReviewForm" style="margin: 15px 0; padding: 10px; background: #f0f8ff; border-radius: 6px;">
                            <h4>{{ selectedStoreForReview?.name }} 리뷰 추가</h4>
                            <input v-model="reviewerReviewUrl" type="url" placeholder="네이버 리뷰 URL" class="input" style="width: 400px; margin-right: 10px;">
                            <button @click="submitReviewerReview" class="btn btn-primary">등록</button>
                            <button @click="showReviewerReviewForm = false" class="btn btn-secondary">취소</button>
                        </div>

                        <!-- 내 리뷰 목록 -->
                        <table class="table">
                            <thead><tr><th>업체명</th><th>URL</th><th>리뷰내용</th><th>영수증날짜</th><th>상태</th></tr></thead>
                            <tbody>
                                <tr v-for="review in myReviews" :key="review.id">
                                    <td style="font-weight: 600;">{{ review.store_name }}</td>
                                    <td style="font-size: 9px;"><a :href="review.review_url" target="_blank">{{ review.review_url.substring(0, 20) }}...</a></td>
                                    <td style="font-size: 10px;">{{ review.extracted_text || '-' }}</td>
                                    <td style="text-align: center;">{{ review.extracted_date || '-' }}</td>
                                    <td><span :class="'status-' + review.status">{{ getStatusText(review.status) }}</span></td>
                                </tr>
                            </tbody>
                        </table>
                        
                        <div style="margin-top: 10px; padding: 8px; background: #fff3cd; border-radius: 4px; text-align: center;">
                            <p style="font-size: 11px; color: #856404;">⚠️ 리뷰 추출은 관리자만 가능합니다</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 상세 모달 -->
        <div v-if="selectedReview" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;" @click="selectedReview = null">
            <div style="background: white; padding: 20px; border-radius: 8px; max-width: 500px; width: 90%;" @click.stop>
                <h4>🔍 {{ selectedReview.store_name }}</h4>
                <div style="margin: 10px 0;"><strong>URL:</strong> <a :href="selectedReview.review_url" target="_blank">{{ selectedReview.review_url }}</a></div>
                <div v-if="selectedReview.extracted_text" style="background: #f0f8ff; padding: 10px; border-radius: 4px; margin: 10px 0;">
                    <strong>리뷰:</strong> {{ selectedReview.extracted_text }}
                </div>
                <div v-if="selectedReview.extracted_date"><strong>날짜:</strong> {{ selectedReview.extracted_date }}</div>
                <button @click="selectedReview = null" class="btn btn-secondary" style="margin-top: 10px;">닫기</button>
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
                    user: null,
                    loginType: 'admin',
                    loginForm: { username: 'admin', password: 'admin123' },
                    
                    tab: 'companies',
                    loading: false,
                    loadingMessage: '처리중...',
                    
                    showAdminReviewForm: false,
                    showReviewerReviewForm: false,
                    
                    companies: [],
                    stores: [],
                    reviewers: [],
                    assignments: [],
                    allReviews: [],
                    myStores: [],
                    myReviews: [],
                    myAssignedStores: [],
                    
                    companyForm: { name: '', password: '' },
                    storeForm: { company_id: '', name: '', start_date: '', daily_count: 1, duration_days: 30 },
                    reviewerForm: { name: '', password: '' },
                    adminReviewForm: { store_id: '', url: '' },
                    assignForm: { reviewer_id: '', store_id: '' },
                    
                    selectedStoreForReview: null,
                    reviewerReviewUrl: '',
                    selectedReview: null
                }
            },
            
            async mounted() {
                await this.loadData();
            },
            
            methods: {
                async loadData() {
                    if (this.user) {
                        try {
                            if (this.user.type === 'admin') {
                                await Promise.all([
                                    this.loadCompanies(),
                                    this.loadStores(),
                                    this.loadReviewers(),
                                    this.loadAssignments(),
                                    this.loadAllReviews()
                                ]);
                            } else if (this.user.type === 'company') {
                                await Promise.all([
                                    this.loadMyStores(),
                                    this.loadMyReviews()
                                ]);
                            } else {
                                await Promise.all([
                                    this.loadMyAssignedStores(),
                                    this.loadMyReviews()
                                ]);
                            }
                        } catch (error) {
                            console.error('데이터 로드 오류:', error);
                        }
                    }
                },
                
                async login() {
                    this.loading = true;
                    try {
                        const response = await axios.post('/auth/login', {
                            type: this.loginType,
                            username: this.loginForm.username,
                            password: this.loginForm.password
                        });
                        
                        this.user = response.data;
                        await this.loadData();
                        alert('✅ 로그인 성공!');
                    } catch (error) {
                        alert('❌ 로그인 실패');
                    } finally {
                        this.loading = false;
                    }
                },
                
                logout() {
                    this.user = null;
                },
                
                async loadCompanies() {
                    const response = await axios.get('/api/companies');
                    this.companies = response.data;
                },
                
                async loadStores() {
                    const response = await axios.get('/api/stores');
                    this.stores = response.data;
                },
                
                async loadReviewers() {
                    const response = await axios.get('/api/reviewers');
                    this.reviewers = response.data;
                },
                
                async loadAssignments() {
                    const response = await axios.get('/api/assignments');
                    this.assignments = response.data;
                },
                
                async loadAllReviews() {
                    const response = await axios.get('/api/all-reviews');
                    this.allReviews = response.data;
                },
                
                async loadMyStores() {
                    const response = await axios.get(`/api/company-stores/${this.user.username}`);
                    this.myStores = response.data;
                },
                
                async loadMyReviews() {
                    const endpoint = this.user.type === 'company' ? 
                                    `/api/company-reviews/${this.user.username}` :
                                    `/api/reviewer-reviews/${this.user.username}`;
                    const response = await axios.get(endpoint);
                    this.myReviews = response.data;
                },
                
                async loadMyAssignedStores() {
                    const response = await axios.get(`/api/reviewer-stores/${this.user.username}`);
                    this.myAssignedStores = response.data;
                },
                
                async createCompany() {
                    if (!this.companyForm.name || !this.companyForm.password) {
                        alert('❌ 고객사명과 비밀번호를 입력하세요');
                        return;
                    }
                    
                    try {
                        await axios.post('/api/create-company', this.companyForm);
                        alert('✅ 고객사 생성 완료!');
                        this.companyForm = { name: '', password: '' };
                        await this.loadCompanies();
                    } catch (error) {
                        alert('❌ 생성 실패');
                    }
                },
                
                async createStore() {
                    if (!this.storeForm.company_id || !this.storeForm.name) {
                        alert('❌ 고객사와 업체명을 입력하세요');
                        return;
                    }
                    
                    try {
                        await axios.post('/api/create-store', this.storeForm);
                        alert('✅ 업체 등록 완료!');
                        this.storeForm = { company_id: '', name: '', start_date: '', daily_count: 1, duration_days: 30 };
                        await this.loadStores();
                    } catch (error) {
                        alert('❌ 등록 실패');
                    }
                },
                
                async createReviewer() {
                    if (!this.reviewerForm.name || !this.reviewerForm.password) {
                        alert('❌ 리뷰어명과 비밀번호를 입력하세요');
                        return;
                    }
                    
                    try {
                        await axios.post('/api/create-reviewer', this.reviewerForm);
                        alert('✅ 리뷰어 생성 완료!');
                        this.reviewerForm = { name: '', password: '' };
                        await this.loadReviewers();
                    } catch (error) {
                        alert('❌ 생성 실패');
                    }
                },
                
                async createAssignment() {
                    if (!this.assignForm.reviewer_id || !this.assignForm.store_id) {
                        alert('❌ 리뷰어와 업체를 선택하세요');
                        return;
                    }
                    
                    try {
                        await axios.post('/api/create-assignment', this.assignForm);
                        alert('✅ 배정 완료!');
                        this.assignForm = { reviewer_id: '', store_id: '' };
                        await this.loadAssignments();
                    } catch (error) {
                        alert('❌ 배정 실패');
                    }
                },
                
                async addAdminReview() {
                    if (!this.adminReviewForm.store_id || !this.adminReviewForm.url) {
                        alert('❌ 업체와 URL을 입력하세요');
                        return;
                    }
                    
                    const store = this.stores.find(s => s.id == this.adminReviewForm.store_id);
                    
                    try {
                        await axios.post('/api/add-review', {
                            store_name: store.name,
                            review_url: this.adminReviewForm.url,
                            registered_by: 'admin',
                            registered_by_type: 'admin'
                        });
                        
                        alert('✅ 리뷰 등록 완료!');
                        this.adminReviewForm = { store_id: '', url: '' };
                        this.showAdminReviewForm = false;
                        await this.loadAllReviews();
                    } catch (error) {
                        alert('❌ 등록 실패');
                    }
                },
                
                addReviewForStore(store) {
                    this.selectedStoreForReview = store;
                    this.showReviewerReviewForm = true;
                },
                
                async submitReviewerReview() {
                    if (!this.reviewerReviewUrl.trim()) {
                        alert('❌ URL을 입력하세요');
                        return;
                    }
                    
                    try {
                        await axios.post('/api/add-review', {
                            store_name: this.selectedStoreForReview.name,
                            review_url: this.reviewerReviewUrl,
                            registered_by: this.user.username,
                            registered_by_type: 'reviewer'
                        });
                        
                        alert('✅ 리뷰 등록 완료!');
                        this.reviewerReviewUrl = '';
                        this.showReviewerReviewForm = false;
                        this.selectedStoreForReview = null;
                        await this.loadMyReviews();
                    } catch (error) {
                        alert('❌ 등록 실패');
                    }
                },
                
                async processReview(reviewId) {
                    if (!confirm('🚀 실제 네이버 리뷰 추출?')) return;
                    
                    this.loading = true;
                    this.loadingMessage = '리뷰 추출 중...';
                    
                    try {
                        await axios.post(`/api/process/${reviewId}`);
                        alert('🚀 추출 시작! 30초 후 확인');
                        setTimeout(() => { 
                            this.loadData(); 
                            this.loading = false; 
                        }, 30000);
                    } catch (error) {
                        alert('❌ 처리 실패');
                        this.loading = false;
                    }
                },
                
                async processAllPending() {
                    const pending = this.allReviews.filter(r => r.status === 'pending');
                    if (pending.length === 0) {
                        alert('처리할 리뷰가 없습니다');
                        return;
                    }
                    
                    if (!confirm(`${pending.length}개 리뷰를 모두 처리?`)) return;
                    
                    try {
                        await axios.post('/api/process-all');
                        alert(`🚀 ${pending.length}개 리뷰 처리 시작!`);
                    } catch (error) {
                        alert('❌ 일괄 처리 실패');
                    }
                },
                
                async exportMyData() {
                    this.loading = true;
                    this.loadingMessage = '리포트 생성 중...';
                    
                    try {
                        const response = await axios.post('/api/export-data', {
                            company_name: this.user.username
                        });
                        
                        if (!response.data.success) {
                            throw new Error(response.data.error);
                        }
                        
                        // CSV 생성
                        const csvData = response.data.data;
                        let csvContent = '\uFEFF업체명,리뷰URL,리뷰내용,영수증날짜\n';
                        
                        csvData.forEach(row => {
                            const csvRow = [
                                row.업체명 || '',
                                row.리뷰URL || '',
                                (row.리뷰내용 || '').replace(/,/g, '，').replace(/\\n/g, ' '),
                                row.영수증날짜 || ''
                            ].join(',');
                            csvContent += csvRow + '\\n';
                        });
                        
                        // 다운로드
                        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                        const url = window.URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = `${this.user.username}_report_${new Date().toISOString().slice(0,10)}.csv`;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        window.URL.revokeObjectURL(url);
                        
                        alert(`✅ 리포트 다운로드 완료! (${response.data.total_count}개)`);
                    } catch (error) {
                        alert('❌ 리포트 생성 실패: ' + error.message);
                    } finally {
                        this.loading = false;
                    }
                },
                
                viewReview(review) {
                    this.selectedReview = review;
                },
                
                // 계산 함수들
                getTotalTargetCount(dailyCount, durationDays) {
                    return (dailyCount || 1) * (durationDays || 30);
                },
                
                getEndDate(startDate, durationDays) {
                    if (!startDate || !durationDays) return '-';
                    const start = new Date(startDate);
                    const end = new Date(start.getTime() + (durationDays - 1) * 24 * 60 * 60 * 1000);
                    return end.toLocaleDateString('ko-KR');
                },
                
                getStoreTargetProgress(storeName, dailyCount, durationDays) {
                    const totalTarget = this.getTotalTargetCount(dailyCount, durationDays);
                    const completed = this.getStoreCompletedCount(storeName);
                    return totalTarget > 0 ? Math.round((completed / totalTarget) * 100) : 0;
                },
                
                getCompanyStoreCount(companyId) {
                    return this.stores.filter(s => s.company_id === companyId).length;
                },
                
                getCompanyReviewCount(companyId) {
                    const companyStores = this.stores.filter(s => s.company_id === companyId);
                    const storeNames = companyStores.map(s => s.name);
                    return this.allReviews.filter(r => storeNames.includes(r.store_name)).length;
                },
                
                getStoreCompletedCount(storeName) {
                    return this.allReviews.filter(r => r.store_name === storeName && r.status === 'completed').length;
                },
                
                getReviewerStores(reviewerId) {
                    const assignments = this.assignments.filter(a => a.reviewer_id === reviewerId);
                    return assignments.map(a => a.store_name).join(', ') || '-';
                },
                
                getReviewerReviewCount(reviewerName) {
                    return this.allReviews.filter(r => r.registered_by === reviewerName).length;
                },
                
                getStatusText(status) {
                    const map = { 'pending': '대기', 'processing': '처리중', 'completed': '완료', 'failed': '실패' };
                    return map[status] || status;
                },
                
                formatDate(dateString) {
                    return new Date(dateString).toLocaleDateString('ko-KR');
                }
            }
        }).mount('#app');
    </script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("네이버 리뷰 관리 시스템 - 안정 버전")
    print(f"접속: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)