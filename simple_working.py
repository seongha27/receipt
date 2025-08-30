from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, Response
import uvicorn
import sqlite3
import hashlib
from datetime import datetime
import csv
from io import StringIO

app = FastAPI()

# 간단한 DB 초기화
def init_db():
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS admin')
    cursor.execute('DROP TABLE IF EXISTS companies') 
    cursor.execute('DROP TABLE IF EXISTS stores')
    cursor.execute('DROP TABLE IF EXISTS reviewers')
    cursor.execute('DROP TABLE IF EXISTS assignments')
    cursor.execute('DROP TABLE IF EXISTS reviews')
    
    cursor.execute('CREATE TABLE admin (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)')
    cursor.execute('CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT UNIQUE, password_hash TEXT)')
    cursor.execute('CREATE TABLE stores (id INTEGER PRIMARY KEY, company_id INTEGER, name TEXT, start_date TEXT, daily_count INTEGER, duration_days INTEGER)')
    cursor.execute('CREATE TABLE reviewers (id INTEGER PRIMARY KEY, name TEXT, password_hash TEXT)')
    cursor.execute('CREATE TABLE assignments (id INTEGER PRIMARY KEY, reviewer_id INTEGER, store_id INTEGER)')
    cursor.execute('CREATE TABLE reviews (id INTEGER PRIMARY KEY, store_name TEXT, review_url TEXT, extracted_text TEXT, extracted_date TEXT, status TEXT DEFAULT "pending", registered_by TEXT)')
    
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute('INSERT INTO admin (username, password_hash) VALUES (?, ?)', ('admin', admin_hash))
    
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>네이버 리뷰 관리 시스템</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
</head>
<body>
    <div id="app">
        <!-- 로그인 -->
        <div v-if="!user" style="max-width: 400px; margin: 100px auto; padding: 30px; background: white; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
            <h2 style="text-align: center; margin-bottom: 20px;">🔐 로그인</h2>
            
            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <button @click="loginType = 'admin'" :style="{background: loginType === 'admin' ? '#dc3545' : '#6c757d', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer'}">관리자</button>
                <button @click="loginType = 'company'" :style="{background: loginType === 'company' ? '#007bff' : '#6c757d', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer'}">고객사</button>
                <button @click="loginType = 'reviewer'" :style="{background: loginType === 'reviewer' ? '#28a745' : '#6c757d', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer'}">리뷰어</button>
            </div>
            
            <input v-model="username" :placeholder="loginType === 'admin' ? 'admin' : loginType === 'company' ? '고객사명' : '리뷰어명'" 
                   style="width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px;">
            <input v-model="password" type="password" :placeholder="loginType === 'admin' ? 'admin123' : '비밀번호'"
                   style="width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 4px;">
            
            <button @click="login" style="width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">로그인</button>
            
            <p style="text-align: center; margin-top: 15px; font-size: 12px; color: #666;">기본 관리자: admin / admin123</p>
        </div>

        <!-- 메인 화면 -->
        <div v-if="user" style="max-width: 1200px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #007bff, #6f42c1); color: white; padding: 20px; text-align: center; border-radius: 10px; margin-bottom: 20px;">
                <h1>{{ user.type === 'admin' ? '🔧 시스템 관리자' : user.type === 'company' ? '🏢 ' + user.username : '👤 ' + user.username }}</h1>
                <button @click="logout" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 8px 16px; border-radius: 15px; cursor: pointer; margin-top: 10px;">로그아웃</button>
            </div>

            <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <!-- 관리자 화면 -->
                <div v-if="user.type === 'admin'">
                    <div style="margin-bottom: 20px;">
                        <button @click="tab = 'companies'" :style="{background: tab === 'companies' ? '#007bff' : '#f8f9fa', color: tab === 'companies' ? 'white' : '#333', border: 'none', padding: '10px 20px', borderRadius: '4px', cursor: 'pointer', marginRight: '5px'}">고객사</button>
                        <button @click="tab = 'stores'" :style="{background: tab === 'stores' ? '#007bff' : '#f8f9fa', color: tab === 'stores' ? 'white' : '#333', border: 'none', padding: '10px 20px', borderRadius: '4px', cursor: 'pointer', marginRight: '5px'}">업체</button>
                        <button @click="tab = 'reviewers'" :style="{background: tab === 'reviewers' ? '#007bff' : '#f8f9fa', color: tab === 'reviewers' ? 'white' : '#333', border: 'none', padding: '10px 20px', borderRadius: '4px', cursor: 'pointer', marginRight: '5px'}">리뷰어</button>
                        <button @click="tab = 'assignments'" :style="{background: tab === 'assignments' ? '#007bff' : '#f8f9fa', color: tab === 'assignments' ? 'white' : '#333', border: 'none', padding: '10px 20px', borderRadius: '4px', cursor: 'pointer', marginRight: '5px'}">배정</button>
                        <button @click="tab = 'reviews'" :style="{background: tab === 'reviews' ? '#007bff' : '#f8f9fa', color: tab === 'reviews' ? 'white' : '#333', border: 'none', padding: '10px 20px', borderRadius: '4px', cursor: 'pointer', marginRight: '5px'}">리뷰관리</button>
                    </div>

                    <!-- 고객사 관리 -->
                    <div v-if="tab === 'companies'">
                        <h3>🏢 고객사 관리</h3>
                        <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                            <input v-model="companyForm.name" placeholder="고객사명" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                            <input v-model="companyForm.password" type="password" placeholder="비밀번호" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                            <button @click="createCompany" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">생성</button>
                        </div>
                        <div v-for="company in companies" :key="company.id" style="padding: 10px; border-bottom: 1px solid #eee;">
                            <strong>{{ company.name }}</strong>
                        </div>
                    </div>

                    <!-- 업체 관리 -->
                    <div v-if="tab === 'stores'">
                        <h3>🏪 업체 관리</h3>
                        <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                            <select v-model="storeForm.company_id" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="">고객사 선택</option>
                                <option v-for="company in companies" :key="company.id" :value="company.id">{{ company.name }}</option>
                            </select>
                            <input v-model="storeForm.name" placeholder="업체명" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                            <input v-model="storeForm.start_date" type="date" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                            <input v-model="storeForm.daily_count" type="number" placeholder="하루갯수" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px; width: 100px;">
                            <input v-model="storeForm.duration_days" type="number" placeholder="일수" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px; width: 80px;">
                            <button @click="createStore" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">등록</button>
                        </div>
                        <div v-for="store in stores" :key="store.id" style="padding: 10px; border-bottom: 1px solid #eee;">
                            <strong>{{ store.name }}</strong> ({{ store.company_name }}) - 목표: {{ getTotalTarget(store.daily_count, store.duration_days) }}개
                        </div>
                    </div>

                    <!-- 리뷰어 관리 -->
                    <div v-if="tab === 'reviewers'">
                        <h3>👥 리뷰어 관리</h3>
                        <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                            <input v-model="reviewerForm.name" placeholder="리뷰어명" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                            <input v-model="reviewerForm.password" type="password" placeholder="비밀번호" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                            <button @click="createReviewer" style="padding: 8px 16px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">생성</button>
                        </div>
                        <div v-for="reviewer in reviewers" :key="reviewer.id" style="padding: 10px; border-bottom: 1px solid #eee;">
                            <strong>{{ reviewer.name }}</strong>
                        </div>
                    </div>

                    <!-- 배정 관리 -->
                    <div v-if="tab === 'assignments'">
                        <h3>🔗 배정 관리</h3>
                        <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                            <select v-model="assignForm.reviewer_id" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="">리뷰어 선택</option>
                                <option v-for="reviewer in reviewers" :key="reviewer.id" :value="reviewer.id">{{ reviewer.name }}</option>
                            </select>
                            <select v-model="assignForm.store_id" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="">업체 선택</option>
                                <option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }}</option>
                            </select>
                            <button @click="createAssignment" style="padding: 8px 16px; background: #ffc107; color: #333; border: none; border-radius: 4px; cursor: pointer;">배정</button>
                        </div>
                        <div v-for="assignment in assignments" :key="assignment.id" style="padding: 10px; border-bottom: 1px solid #eee;">
                            {{ assignment.reviewer_name }} → {{ assignment.store_name }}
                        </div>
                    </div>

                    <!-- 리뷰 관리 -->
                    <div v-if="tab === 'reviews'">
                        <h3>📝 리뷰 관리</h3>
                        <div style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                            <select v-model="reviewForm.store_id" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="">업체 선택</option>
                                <option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }}</option>
                            </select>
                            <input v-model="reviewForm.url" type="url" placeholder="리뷰 URL" style="padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px; width: 300px;">
                            <button @click="addReview" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">등록</button>
                            <button @click="processAll" style="padding: 8px 16px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; margin-left: 10px;">전체처리</button>
                        </div>
                        <div v-for="review in allReviews" :key="review.id" style="padding: 10px; border-bottom: 1px solid #eee;">
                            <strong>{{ review.store_name }}</strong> - {{ review.status }}
                            <button v-if="review.status === 'pending'" @click="processReview(review.id)" style="margin-left: 10px; padding: 4px 8px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer;">▶️</button>
                        </div>
                    </div>
                </div>

                <!-- 고객사 화면 -->
                <div v-if="user.type === 'company'">
                    <h3>🏢 {{ user.username }} 리뷰 현황</h3>
                    <button @click="downloadCSV" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; margin: 15px 0;">📊 CSV 다운로드</button>
                    
                    <div v-for="store in myStores" :key="store.id" style="margin: 15px 0; padding: 15px; background: #e8f5e8; border-radius: 8px;">
                        <h4>{{ store.name }}</h4>
                        <p>목표: {{ getTotalTarget(store.daily_count, store.duration_days) }}개</p>
                        <p>완료: {{ getStoreCompleted(store.name) }}개</p>
                        <p>진행률: {{ getStoreCompleted(store.name) }}/{{ getTotalTarget(store.daily_count, store.duration_days) }}</p>
                    </div>
                    
                    <h4>완료된 리뷰</h4>
                    <div v-for="review in myReviews.filter(r => r.status === 'completed')" :key="review.id" style="padding: 8px; border-bottom: 1px solid #eee;">
                        <strong>{{ review.store_name }}</strong><br>
                        <small>{{ review.review_url.substring(0, 50) }}...</small><br>
                        {{ review.extracted_text }}<br>
                        <strong>날짜: {{ review.extracted_date }}</strong>
                    </div>
                </div>

                <!-- 리뷰어 화면 -->
                <div v-if="user.type === 'reviewer'">
                    <h3>👤 {{ user.username }} 리뷰 등록</h3>
                    
                    <div v-for="store in myStores" :key="store.id" style="margin: 10px 0; padding: 10px; background: #e3f2fd; border-radius: 6px;">
                        {{ store.name }}
                        <button @click="showReviewForm = store.name" style="margin-left: 10px; padding: 4px 8px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer;">+ 리뷰</button>
                    </div>
                    
                    <div v-if="showReviewForm" style="margin: 15px 0; padding: 15px; background: #f0f8ff; border-radius: 8px;">
                        <h4>{{ showReviewForm }} 리뷰 추가</h4>
                        <input v-model="reviewerUrl" type="url" placeholder="네이버 리뷰 URL" style="width: 400px; padding: 8px; margin-right: 10px; border: 1px solid #ddd; border-radius: 4px;">
                        <button @click="addReviewerReview" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">등록</button>
                        <button @click="showReviewForm = null" style="padding: 8px 16px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">취소</button>
                    </div>
                    
                    <div v-for="review in myReviews" :key="review.id" style="padding: 8px; border-bottom: 1px solid #eee;">
                        <strong>{{ review.store_name }}</strong> - {{ review.status }}
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
                    loginType: 'admin',
                    username: 'admin',
                    password: 'admin123',
                    
                    tab: 'companies',
                    
                    companies: [],
                    stores: [],
                    reviewers: [],
                    assignments: [],
                    allReviews: [],
                    myStores: [],
                    myReviews: [],
                    
                    companyForm: { name: '', password: '' },
                    storeForm: { company_id: '', name: '', start_date: '', daily_count: 1, duration_days: 30 },
                    reviewerForm: { name: '', password: '' },
                    reviewForm: { store_id: '', url: '' },
                    assignForm: { reviewer_id: '', store_id: '' },
                    
                    showReviewForm: null,
                    reviewerUrl: ''
                }
            },
            
            methods: {
                async login() {
                    try {
                        const response = await axios.post('/auth/login', {
                            type: this.loginType,
                            username: this.username,
                            password: this.password
                        });
                        
                        this.user = response.data;
                        await this.loadData();
                        alert('로그인 성공!');
                    } catch (error) {
                        alert('로그인 실패');
                    }
                },
                
                logout() {
                    this.user = null;
                    this.username = 'admin';
                    this.password = 'admin123';
                },
                
                async loadData() {
                    if (!this.user) return;
                    
                    try {
                        if (this.user.type === 'admin') {
                            const [companies, stores, reviewers, assignments, reviews] = await Promise.all([
                                axios.get('/api/companies'),
                                axios.get('/api/stores'),
                                axios.get('/api/reviewers'),
                                axios.get('/api/assignments'),
                                axios.get('/api/all-reviews')
                            ]);
                            
                            this.companies = companies.data;
                            this.stores = stores.data;
                            this.reviewers = reviewers.data;
                            this.assignments = assignments.data;
                            this.allReviews = reviews.data;
                            
                        } else if (this.user.type === 'company') {
                            const [stores, reviews] = await Promise.all([
                                axios.get(`/api/company-stores/${this.user.username}`),
                                axios.get(`/api/company-reviews/${this.user.username}`)
                            ]);
                            
                            this.myStores = stores.data;
                            this.myReviews = reviews.data;
                            
                        } else {
                            const [stores, reviews] = await Promise.all([
                                axios.get(`/api/reviewer-stores/${this.user.username}`),
                                axios.get(`/api/reviewer-reviews/${this.user.username}`)
                            ]);
                            
                            this.myStores = stores.data;
                            this.myReviews = reviews.data;
                        }
                    } catch (error) {
                        console.error('데이터 로드 오류:', error);
                    }
                },
                
                async createCompany() {
                    try {
                        await axios.post('/api/create-company', this.companyForm);
                        alert('고객사 생성 완료!');
                        this.companyForm = { name: '', password: '' };
                        await this.loadData();
                    } catch (error) {
                        alert('생성 실패');
                    }
                },
                
                async createStore() {
                    try {
                        await axios.post('/api/create-store', this.storeForm);
                        alert('업체 등록 완료!');
                        this.storeForm = { company_id: '', name: '', start_date: '', daily_count: 1, duration_days: 30 };
                        await this.loadData();
                    } catch (error) {
                        alert('등록 실패');
                    }
                },
                
                async createReviewer() {
                    try {
                        await axios.post('/api/create-reviewer', this.reviewerForm);
                        alert('리뷰어 생성 완료!');
                        this.reviewerForm = { name: '', password: '' };
                        await this.loadData();
                    } catch (error) {
                        alert('생성 실패');
                    }
                },
                
                async createAssignment() {
                    try {
                        await axios.post('/api/create-assignment', this.assignForm);
                        alert('배정 완료!');
                        this.assignForm = { reviewer_id: '', store_id: '' };
                        await this.loadData();
                    } catch (error) {
                        alert('배정 실패');
                    }
                },
                
                async addReview() {
                    const store = this.stores.find(s => s.id == this.reviewForm.store_id);
                    try {
                        await axios.post('/api/add-review', {
                            store_name: store.name,
                            review_url: this.reviewForm.url,
                            registered_by: 'admin'
                        });
                        alert('리뷰 등록 완료!');
                        this.reviewForm = { store_id: '', url: '' };
                        await this.loadData();
                    } catch (error) {
                        alert('등록 실패');
                    }
                },
                
                async addReviewerReview() {
                    try {
                        await axios.post('/api/add-review', {
                            store_name: this.showReviewForm,
                            review_url: this.reviewerUrl,
                            registered_by: this.user.username
                        });
                        alert('리뷰 등록 완료!');
                        this.reviewerUrl = '';
                        this.showReviewForm = null;
                        await this.loadData();
                    } catch (error) {
                        alert('등록 실패');
                    }
                },
                
                async processReview(reviewId) {
                    if (!confirm('리뷰 추출?')) return;
                    
                    try {
                        await axios.post(`/api/process/${reviewId}`);
                        alert('추출 시작! 30초 후 확인');
                        setTimeout(() => this.loadData(), 30000);
                    } catch (error) {
                        alert('처리 실패');
                    }
                },
                
                async processAll() {
                    try {
                        await axios.post('/api/process-all');
                        alert('전체 처리 시작!');
                    } catch (error) {
                        alert('처리 실패');
                    }
                },
                
                async downloadCSV() {
                    try {
                        const response = await axios.post('/api/export-data', {
                            company_name: this.user.username
                        });
                        
                        if (!response.data.success) {
                            throw new Error(response.data.error);
                        }
                        
                        // CSV 생성
                        let csvContent = '\uFEFF업체명,리뷰URL,리뷰내용,영수증날짜\n';
                        
                        response.data.data.forEach(row => {
                            const csvRow = [
                                row.업체명 || '',
                                row.리뷰URL || '',
                                (row.리뷰내용 || '').replace(/,/g, '，'),
                                row.영수증날짜 || ''
                            ].join(',');
                            csvContent += csvRow + '\n';
                        });
                        
                        // 다운로드
                        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                        const url = window.URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = `${this.user.username}_report.csv`;
                        link.click();
                        window.URL.revokeObjectURL(url);
                        
                        alert(`CSV 다운로드 완료! (${response.data.total_count}개)`);
                    } catch (error) {
                        alert('다운로드 실패: ' + error.message);
                    }
                },
                
                getTotalTarget(daily, days) {
                    return (daily || 1) * (days || 30);
                },
                
                getStoreCompleted(storeName) {
                    return this.myReviews.filter(r => r.store_name === storeName && r.status === 'completed').length;
                }
            }
        }).mount('#app');
    </script>
</body>
</html>""")

# API들 (기존과 동일하지만 간단하게)
@app.post("/auth/login")
async def login(data: dict):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(data["password"].encode()).hexdigest()
    
    if data["type"] == "admin":
        cursor.execute('SELECT * FROM admin WHERE username = ? AND password_hash = ?', (data["username"], password_hash))
        user = cursor.fetchone()
        if user:
            conn.close()
            return {"id": user[0], "username": user[1], "type": "admin"}
    elif data["type"] == "company":
        cursor.execute('SELECT * FROM companies WHERE name = ? AND password_hash = ?', (data["username"], password_hash))
        user = cursor.fetchone()
        if user:
            conn.close()
            return {"id": user[0], "username": user[1], "type": "company"}
    elif data["type"] == "reviewer":
        cursor.execute('SELECT * FROM reviewers WHERE name = ? AND password_hash = ?', (data["username"], password_hash))
        user = cursor.fetchone()
        if user:
            conn.close()
            return {"id": user[0], "username": user[1], "type": "reviewer"}
    
    conn.close()
    raise HTTPException(status_code=401, detail="로그인 실패")

@app.get("/api/companies")
async def get_companies():
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies')
    companies = cursor.fetchall()
    conn.close()
    return [{"id": c[0], "name": c[1]} for c in companies]

@app.get("/api/stores")
async def get_stores():
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*, c.name as company_name
        FROM stores s
        LEFT JOIN companies c ON s.company_id = c.id
    ''')
    stores = cursor.fetchall()
    conn.close()
    return [{
        "id": s[0], "company_id": s[1], "name": s[2], "start_date": s[3],
        "daily_count": s[4], "duration_days": s[5], "company_name": s[6]
    } for s in stores]

@app.get("/api/reviewers")
async def get_reviewers():
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reviewers')
    reviewers = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in reviewers]

@app.get("/api/assignments")
async def get_assignments():
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, r.name as reviewer_name, s.name as store_name
        FROM assignments a
        LEFT JOIN reviewers r ON a.reviewer_id = r.id
        LEFT JOIN stores s ON a.store_id = s.id
    ''')
    assignments = cursor.fetchall()
    conn.close()
    return [{"id": a[0], "reviewer_name": a[1], "store_name": a[2]} for a in assignments]

@app.get("/api/all-reviews")
async def get_all_reviews():
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reviews')
    reviews = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "store_name": r[1], "review_url": r[2], "extracted_text": r[3],
        "extracted_date": r[4], "status": r[5], "registered_by": r[6]
    } for r in reviews]

@app.get("/api/company-stores/{company_name}")
async def get_company_stores(company_name: str):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.* FROM stores s
        LEFT JOIN companies c ON s.company_id = c.id
        WHERE c.name = ?
    ''', (company_name,))
    stores = cursor.fetchall()
    conn.close()
    return [{"id": s[0], "name": s[2], "daily_count": s[4], "duration_days": s[5]} for s in stores]

@app.get("/api/company-reviews/{company_name}")
async def get_company_reviews(company_name: str):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.* FROM reviews r
        JOIN stores s ON r.store_name = s.name
        JOIN companies c ON s.company_id = c.id
        WHERE c.name = ?
    ''', (company_name,))
    reviews = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "store_name": r[1], "review_url": r[2], "extracted_text": r[3],
        "extracted_date": r[4], "status": r[5]
    } for r in reviews]

@app.get("/api/reviewer-stores/{reviewer_name}")
async def get_reviewer_stores(reviewer_name: str):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.name FROM assignments a
        LEFT JOIN reviewers r ON a.reviewer_id = r.id
        LEFT JOIN stores s ON a.store_id = s.id
        WHERE r.name = ?
    ''', (reviewer_name,))
    stores = cursor.fetchall()
    conn.close()
    return [{"id": s[0], "name": s[1]} for s in stores if s[1]]

@app.get("/api/reviewer-reviews/{reviewer_name}")
async def get_reviewer_reviews(reviewer_name: str):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reviews WHERE registered_by = ?', (reviewer_name,))
    reviews = cursor.fetchall()
    conn.close()
    return [{
        "id": r[0], "store_name": r[1], "review_url": r[2], "extracted_text": r[3],
        "extracted_date": r[4], "status": r[5]
    } for r in reviews]

@app.post("/api/create-company")
async def create_company(data: dict):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    password_hash = hashlib.sha256(data["password"].encode()).hexdigest()
    cursor.execute('INSERT INTO companies (name, password_hash) VALUES (?, ?)', (data["name"], password_hash))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/create-store")
async def create_store(data: dict):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO stores (company_id, name, start_date, daily_count, duration_days) VALUES (?, ?, ?, ?, ?)',
                  (data["company_id"], data["name"], data.get("start_date"), data.get("daily_count", 1), data.get("duration_days", 30)))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/create-reviewer")
async def create_reviewer(data: dict):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    password_hash = hashlib.sha256(data["password"].encode()).hexdigest()
    cursor.execute('INSERT INTO reviewers (name, password_hash) VALUES (?, ?)', (data["name"], password_hash))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/create-assignment")
async def create_assignment(data: dict):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO assignments (reviewer_id, store_id) VALUES (?, ?)', (data["reviewer_id"], data["store_id"]))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/add-review")
async def add_review(data: dict):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    url_type = "direct" if "/my/review/" in data["review_url"] else "shortcut"
    cursor.execute('INSERT INTO reviews (store_name, review_url, registered_by, status) VALUES (?, ?, ?, "pending")',
                  (data["store_name"], data["review_url"], data["registered_by"]))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/export-data")
async def export_data(data: dict):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    
    # 해당 고객사의 완료된 리뷰만
    cursor.execute('''
        SELECT r.store_name, r.review_url, r.extracted_text, r.extracted_date
        FROM reviews r
        JOIN stores s ON r.store_name = s.name
        JOIN companies c ON s.company_id = c.id
        WHERE c.name = ? AND r.status = "completed"
    ''', (data["company_name"],))
    
    reviews = cursor.fetchall()
    conn.close()
    
    return {
        "success": True,
        "data": [{"업체명": r[0], "리뷰URL": r[1], "리뷰내용": r[2], "영수증날짜": r[3]} for r in reviews],
        "total_count": len(reviews)
    }

@app.post("/api/process/{review_id}")
async def process_review(review_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(extract_review_bg, review_id)
    return {"success": True}

@app.post("/api/process-all")
async def process_all(background_tasks: BackgroundTasks):
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM reviews WHERE status = "pending"')
    pending = cursor.fetchall()
    conn.close()
    
    for review in pending:
        background_tasks.add_task(extract_review_bg, review[0])
    
    return {"success": True}

def extract_review_bg(review_id: int):
    """실제 네이버 리뷰 추출"""
    conn = sqlite3.connect('simple.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT store_name, review_url FROM reviews WHERE id = ?', (review_id,))
        result = cursor.fetchone()
        if not result:
            return
        
        store_name, review_url = result
        cursor.execute('UPDATE reviews SET status = "processing" WHERE id = ?', (review_id,))
        conn.commit()
        
        print(f"추출 시작: {store_name} - {review_url}")
        
        # 실제 Selenium 추출
        try:
            from selenium import webdriver
            from selenium.webdriver.support.ui import WebDriverWait
            from bs4 import BeautifulSoup
            import time
            
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            driver = webdriver.Chrome(options=options)
            driver.get(review_url)
            
            if "/my/review/" in review_url:
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                review_elem = soup.find('a', {'data-pui-click-code': 'reviewend.text'})
                text = review_elem.get_text(strip=True) if review_elem else "본문 없음"
                
                time_elem = soup.find('time', {'aria-hidden': 'true'})
                date = time_elem.get_text(strip=True) if time_elem else "날짜 없음"
            else:
                if "naver.me" in review_url:
                    WebDriverWait(driver, 10).until(lambda d: d.current_url != review_url)
                
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                target_review = None
                
                review_blocks = soup.find_all('div', class_='hahVh2')
                for block in review_blocks:
                    shop_elem = block.find('span', class_='pui__pv1E2a')
                    if shop_elem and shop_elem.text.strip() == store_name:
                        target_review = block
                        break
                
                if target_review:
                    review_div = target_review.find('div', class_='pui__vn15t2')
                    text = review_div.text.strip() if review_div else "본문 없음"
                    
                    time_elem = target_review.find('time', {'aria-hidden': 'true'})
                    date = time_elem.text.strip() if time_elem else "날짜 없음"
                else:
                    text = f"'{store_name}' 업체를 찾을 수 없음"
                    date = "날짜 없음"
            
            driver.quit()
            
            status = 'completed' if "없음" not in text else 'failed'
            cursor.execute('UPDATE reviews SET status = ?, extracted_text = ?, extracted_date = ? WHERE id = ?',
                          (status, text, date, review_id))
            
            print(f"추출 완료: {store_name} - {status}")
            
        except Exception as e:
            print(f"추출 실패: {e}")
            cursor.execute('UPDATE reviews SET status = "failed" WHERE id = ?', (review_id,))
        
        conn.commit()
        
    except Exception as e:
        print(f"오류: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("간단 버전 시작!")
    uvicorn.run(app, host="0.0.0.0", port=8000)