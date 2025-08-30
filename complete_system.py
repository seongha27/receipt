from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn
import os
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
import sys
import io
import pandas as pd
from io import BytesIO
import openpyxl

# 유니코드 출력을 위한 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = FastAPI(title="네이버 리뷰 관리 시스템 - 완전 기능")

def init_complete_database():
    """완전한 데이터베이스 초기화"""
    # 기존 파일들 정리
    for db_file in ['reviews.db', 'real_reviews.db', 'sheet_style_reviews.db']:
        if os.path.exists(db_file):
            os.remove(db_file)
    
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    
    # 슈퍼 관리자 테이블 (시스템 관리자)
    cursor.execute('''
        CREATE TABLE super_admin (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 고객사 테이블
    cursor.execute('''
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            subscription_plan TEXT DEFAULT 'basic',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 사용자 테이블 (고객사별)
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'reviewer',
            email TEXT,
            phone TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # 업체 테이블 (상세 정보 포함)
    cursor.execute('''
        CREATE TABLE stores (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            location TEXT,
            category TEXT,
            naver_place_url TEXT,
            
            -- 캠페인 설정
            campaign_start_date DATE,
            daily_target_count INTEGER DEFAULT 1,
            campaign_duration_days INTEGER DEFAULT 30,
            
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # 업체-리뷰어 배정 테이블
    cursor.execute('''
        CREATE TABLE store_assignments (
            id INTEGER PRIMARY KEY,
            store_id INTEGER,
            reviewer_id INTEGER,
            assigned_by INTEGER,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (store_id) REFERENCES stores (id),
            FOREIGN KEY (reviewer_id) REFERENCES users (id),
            FOREIGN KEY (assigned_by) REFERENCES users (id)
        )
    ''')
    
    # 리뷰 테이블 (구글시트 호환)
    cursor.execute('''
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            store_id INTEGER,
            registered_by_user_id INTEGER,
            
            -- 구글시트 컬럼
            store_name TEXT NOT NULL,           -- A열
            review_url TEXT NOT NULL,           -- B열  
            extracted_review_text TEXT,         -- C열
            extracted_receipt_date TEXT,        -- D열
            registration_date TEXT,             -- E열
            status TEXT DEFAULT 'pending',      -- F열
            
            -- 메타데이터
            url_type TEXT,
            error_message TEXT,
            processing_attempts INTEGER DEFAULT 0,
            extracted_reviewer_name TEXT,
            extracted_rating INTEGER,
            extracted_visit_date TEXT,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (store_id) REFERENCES stores (id),
            FOREIGN KEY (registered_by_user_id) REFERENCES users (id)
        )
    ''')
    
    # 데이터 내보내기 기록
    cursor.execute('''
        CREATE TABLE export_logs (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            exported_by INTEGER,
            export_type TEXT,
            file_name TEXT,
            record_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (exported_by) REFERENCES users (id)
        )
    ''')
    
    # 슈퍼 관리자 계정 생성
    super_admin_hash = hashlib.sha256("superadmin123".encode()).hexdigest()
    cursor.execute('''
        INSERT INTO super_admin (username, password_hash, full_name) 
        VALUES (?, ?, ?)
    ''', ('superadmin', super_admin_hash, '시스템 관리자'))
    
    conn.commit()
    conn.close()
    print("✅ 완전한 관리 시스템 데이터베이스 생성 완료!")

# 초기화 실행
init_complete_database()

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>네이버 리뷰 관리 시스템 - 완전 관리</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; }
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 0; text-align: center; margin-bottom: 30px; }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px; margin-bottom: 25px; }
        .btn { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; transition: all 0.3s; margin: 3px; }
        .btn-primary { background: #667eea; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-warning { background: #ffc107; color: #333; }
        .btn-secondary { background: #6c757d; color: white; }
        .input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; margin: 5px 0; }
        .input:focus { border-color: #667eea; outline: none; box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2); }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
        .form-row.single { grid-template-columns: 1fr; }
        .status-pending { background: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 12px; font-size: 11px; }
        .status-processing { background: #cce5ff; color: #004085; padding: 4px 8px; border-radius: 12px; font-size: 11px; }
        .status-completed { background: #d4edda; color: #155724; padding: 4px 8px; border-radius: 12px; font-size: 11px; }
        .status-failed { background: #f8d7da; color: #721c24; padding: 4px 8px; border-radius: 12px; font-size: 11px; }
        .tab { padding: 12px 20px; background: #f8f9fa; border: none; cursor: pointer; margin-right: 5px; border-radius: 8px 8px 0 0; font-weight: 600; }
        .tab.active { background: white; border-bottom: 3px solid #667eea; color: #667eea; }
        .sheet-table { width: 100%; border-collapse: collapse; background: white; font-size: 13px; }
        .sheet-table th { background: #f8f9fa; border: 1px solid #ddd; padding: 8px; font-weight: 600; text-align: center; }
        .sheet-table td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
        .login-card { background: white; border-radius: 15px; padding: 30px; max-width: 400px; margin: 50px auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        [v-cloak] { display: none; }
    </style>
</head>
<body>
    <div id="app" v-cloak>
        <!-- 시스템 관리자 로그인 -->
        <div v-if="!isLoggedIn" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center;">
            <div class="login-card">
                <h2 style="text-align: center; margin-bottom: 30px; color: #333;">
                    {{ loginMode === 'super' ? '🔧 시스템 관리자' : loginMode === 'company' ? '🏢 고객사 관리자' : '👥 리뷰어 로그인' }}
                </h2>
                
                <!-- 로그인 모드 선택 -->
                <div style="display: flex; gap: 8px; margin-bottom: 25px;">
                    <button @click="loginMode = 'super'" :class="loginMode === 'super' ? 'btn-danger' : 'btn-secondary'" 
                            style="flex: 1; font-size: 12px; padding: 8px;">관리자</button>
                    <button @click="loginMode = 'company'" :class="loginMode === 'company' ? 'btn-primary' : 'btn-secondary'" 
                            style="flex: 1; font-size: 12px; padding: 8px;">고객사</button>
                    <button @click="loginMode = 'reviewer'" :class="loginMode === 'reviewer' ? 'btn-success' : 'btn-secondary'" 
                            style="flex: 1; font-size: 12px; padding: 8px;">리뷰어</button>
                </div>
                
                <!-- 고객사 선택 (고객사/리뷰어 로그인시) -->
                <div v-if="loginMode !== 'super'" style="margin-bottom: 20px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600;">고객사 선택</label>
                    <select v-model="selectedCompanyId" class="input" required>
                        <option value="">고객사를 선택하세요</option>
                        <option v-for="company in companies" :key="company.id" :value="company.id">
                            {{ company.display_name }}
                        </option>
                    </select>
                </div>
                
                <div class="form-row single">
                    <div>
                        <label style="display: block; margin-bottom: 8px; font-weight: 600;">사용자명</label>
                        <input v-model="loginForm.username" type="text" class="input" 
                               :placeholder="loginMode === 'super' ? 'superadmin' : 'admin 또는 계정명'">
                    </div>
                </div>
                
                <div class="form-row single">
                    <div>
                        <label style="display: block; margin-bottom: 8px; font-weight: 600;">비밀번호</label>
                        <input v-model="loginForm.password" type="password" class="input" 
                               :placeholder="loginMode === 'super' ? 'superadmin123' : '비밀번호'">
                    </div>
                </div>
                
                <button @click="login" class="btn btn-primary" style="width: 100%; font-size: 16px; padding: 15px; margin-top: 15px;">
                    로그인
                </button>
                
                <div style="margin-top: 25px; padding: 20px; background: #f8f9fa; border-radius: 10px; text-align: center;">
                    <p style="font-size: 12px; color: #666; margin-bottom: 10px;">
                        <strong>시스템 관리자:</strong> superadmin / superadmin123
                    </p>
                    <p style="font-size: 12px; color: #666;">
                        고객사별 계정은 시스템 관리자가 생성합니다
                    </p>
                </div>
            </div>
        </div>

        <!-- 메인 시스템 -->
        <div v-if="isLoggedIn">
            <div class="header">
                <h1 style="font-size: 2.5rem; margin-bottom: 10px;">
                    {{ userType === 'super' ? '🔧 시스템 관리자' : '🏢 ' + (currentUser.company_name || '') }}
                </h1>
                <p style="opacity: 0.9;">
                    {{ userType === 'super' ? '전체 시스템 관리' : userType === 'company' ? '고객사 관리자' : '리뷰어' }}
                </p>
                <button @click="logout" style="margin-top: 15px; background: rgba(255,255,255,0.2); border: none; color: white; padding: 10px 20px; border-radius: 20px; cursor: pointer;">
                    로그아웃
                </button>
            </div>

            <div class="container">
                <!-- 시스템 관리자 페이지 -->
                <div v-if="userType === 'super'">
                    <div class="card">
                        <div style="display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #eee; padding-bottom: 15px;">
                            <button @click="adminTab = 'companies'" :class="adminTab === 'companies' ? 'tab active' : 'tab'">
                                🏢 고객사 관리
                            </button>
                            <button @click="adminTab = 'stores'" :class="adminTab === 'stores' ? 'tab active' : 'tab'">
                                🏪 업체 관리
                            </button>
                            <button @click="adminTab = 'reviewers'" :class="adminTab === 'reviewers' ? 'tab active' : 'tab'">
                                👥 리뷰어 관리
                            </button>
                            <button @click="adminTab = 'assignments'" :class="adminTab === 'assignments' ? 'tab active' : 'tab'">
                                🔗 배정 관리
                            </button>
                            <button @click="adminTab = 'bulk'" :class="adminTab === 'bulk' ? 'tab active' : 'tab'">
                                📊 대량 업로드
                            </button>
                        </div>

                        <!-- 고객사 관리 -->
                        <div v-if="adminTab === 'companies'">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <h3>🏢 고객사 계정 관리</h3>
                                <button @click="showCompanyForm = !showCompanyForm" class="btn btn-primary">
                                    {{ showCompanyForm ? '폼 닫기' : '+ 새 고객사 추가' }}
                                </button>
                            </div>

                            <!-- 고객사 추가 폼 -->
                            <div v-if="showCompanyForm" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                                <h4 style="margin-bottom: 15px;">새 고객사 계정 생성</h4>
                                <div class="form-row">
                                    <div>
                                        <label style="font-weight: 600;">고객사 ID *</label>
                                        <input v-model="companyForm.name" type="text" class="input" placeholder="예: adsketch">
                                    </div>
                                    <div>
                                        <label style="font-weight: 600;">표시명 *</label>
                                        <input v-model="companyForm.display_name" type="text" class="input" placeholder="예: 애드스케치">
                                    </div>
                                </div>
                                <div class="form-row">
                                    <div>
                                        <label style="font-weight: 600;">이메일</label>
                                        <input v-model="companyForm.contact_email" type="email" class="input" placeholder="admin@company.com">
                                    </div>
                                    <div>
                                        <label style="font-weight: 600;">전화번호</label>
                                        <input v-model="companyForm.contact_phone" type="text" class="input" placeholder="02-1234-5678">
                                    </div>
                                </div>
                                <div class="form-row single" style="margin-bottom: 20px;">
                                    <div>
                                        <label style="font-weight: 600;">관리자 계정</label>
                                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                                            <input v-model="companyForm.admin_username" type="text" class="input" placeholder="관리자 ID">
                                            <input v-model="companyForm.admin_password" type="password" class="input" placeholder="비밀번호">
                                        </div>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 10px;">
                                    <button @click="createCompany" class="btn btn-primary" style="flex: 1;">고객사 생성</button>
                                    <button @click="resetCompanyForm" class="btn btn-secondary">초기화</button>
                                    <button @click="showCompanyForm = false" class="btn btn-secondary">취소</button>
                                </div>
                            </div>

                            <!-- 고객사 목록 -->
                            <div style="overflow-x: auto;">
                                <table class="sheet-table">
                                    <thead>
                                        <tr>
                                            <th>ID</th>
                                            <th>고객사명</th>
                                            <th>이메일</th>
                                            <th>전화번호</th>
                                            <th>생성일</th>
                                            <th>상태</th>
                                            <th>작업</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="company in allCompanies" :key="company.id">
                                            <td style="font-weight: 600;">{{ company.name }}</td>
                                            <td>{{ company.display_name }}</td>
                                            <td>{{ company.contact_email || '-' }}</td>
                                            <td>{{ company.contact_phone || '-' }}</td>
                                            <td style="font-size: 12px;">{{ formatDate(company.created_at) }}</td>
                                            <td>
                                                <span :class="company.is_active ? 'status-completed' : 'status-failed'">
                                                    {{ company.is_active ? '활성' : '비활성' }}
                                                </span>
                                            </td>
                                            <td>
                                                <button @click="viewCompanyDetail(company)" class="btn btn-success" style="font-size: 11px; padding: 5px 10px;">
                                                    👁️ 상세
                                                </button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- 업체 관리 -->
                        <div v-if="adminTab === 'stores'">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <h3>🏪 업체 관리</h3>
                                <button @click="showStoreForm = !showStoreForm" class="btn btn-primary">
                                    {{ showStoreForm ? '폼 닫기' : '+ 새 업체 추가' }}
                                </button>
                            </div>

                            <!-- 업체 추가 폼 -->
                            <div v-if="showStoreForm" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                                <h4 style="margin-bottom: 15px;">새 업체 등록</h4>
                                <div class="form-row">
                                    <div>
                                        <label style="font-weight: 600;">소속 고객사 *</label>
                                        <select v-model="storeForm.company_id" class="input" required>
                                            <option value="">고객사 선택</option>
                                            <option v-for="company in allCompanies" :key="company.id" :value="company.id">
                                                {{ company.display_name }}
                                            </option>
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-weight: 600;">업체명 *</label>
                                        <input v-model="storeForm.name" type="text" class="input" placeholder="정확한 네이버 업체명">
                                    </div>
                                </div>
                                <div class="form-row">
                                    <div>
                                        <label style="font-weight: 600;">업종</label>
                                        <select v-model="storeForm.category" class="input">
                                            <option value="">업종 선택</option>
                                            <option value="카페">☕ 카페</option>
                                            <option value="음식점">🍽️ 음식점</option>
                                            <option value="서비스업">🛎️ 서비스업</option>
                                            <option value="소매업">🛍️ 소매업</option>
                                            <option value="기타">📦 기타</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-weight: 600;">위치</label>
                                        <input v-model="storeForm.location" type="text" class="input" placeholder="서울 강남구">
                                    </div>
                                </div>
                                
                                <!-- 캠페인 설정 -->
                                <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 15px 0;">
                                    <h5 style="margin-bottom: 12px; color: #155724;">📅 캠페인 설정</h5>
                                    <div class="form-row">
                                        <div>
                                            <label style="font-weight: 600;">시작일</label>
                                            <input v-model="storeForm.campaign_start_date" type="date" class="input">
                                        </div>
                                        <div>
                                            <label style="font-weight: 600;">하루 목표 갯수</label>
                                            <input v-model="storeForm.daily_target_count" type="number" class="input" placeholder="1" min="1">
                                        </div>
                                    </div>
                                    <div class="form-row single">
                                        <div>
                                            <label style="font-weight: 600;">캠페인 기간 (일수)</label>
                                            <input v-model="storeForm.campaign_duration_days" type="number" class="input" placeholder="30" min="1">
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="form-row single">
                                    <div>
                                        <label style="font-weight: 600;">설명</label>
                                        <textarea v-model="storeForm.description" class="input" rows="2" placeholder="업체 설명"></textarea>
                                    </div>
                                </div>
                                
                                <div style="display: flex; gap: 10px; margin-top: 20px;">
                                    <button @click="createStore" class="btn btn-primary" style="flex: 1;">업체 등록</button>
                                    <button @click="resetStoreForm" class="btn btn-secondary">초기화</button>
                                    <button @click="showStoreForm = false" class="btn btn-secondary">취소</button>
                                </div>
                            </div>

                            <!-- 업체 목록 -->
                            <div style="overflow-x: auto;">
                                <table class="sheet-table">
                                    <thead>
                                        <tr>
                                            <th>업체명</th>
                                            <th>고객사</th>
                                            <th>업종</th>
                                            <th>위치</th>
                                            <th>캠페인 기간</th>
                                            <th>일일 목표</th>
                                            <th>리뷰 수</th>
                                            <th>작업</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="store in allStores" :key="store.id">
                                            <td style="font-weight: 600;">{{ store.name }}</td>
                                            <td>{{ store.company_name }}</td>
                                            <td>{{ store.category || '-' }}</td>
                                            <td>{{ store.location || '-' }}</td>
                                            <td style="font-size: 12px;">
                                                {{ store.campaign_start_date ? formatDate(store.campaign_start_date) + ' (' + store.campaign_duration_days + '일)' : '-' }}
                                            </td>
                                            <td style="text-align: center;">{{ store.daily_target_count || 1 }}개/일</td>
                                            <td style="text-align: center; font-weight: 600;">{{ getStoreReviewCount(store.id) }}개</td>
                                            <td>
                                                <button @click="viewStoreDetail(store)" class="btn btn-success" style="font-size: 11px; padding: 5px 8px;">
                                                    👁️ 상세
                                                </button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- 리뷰어 관리 -->
                        <div v-if="adminTab === 'reviewers'">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <h3>👥 리뷰어 계정 관리</h3>
                                <button @click="showReviewerForm = !showReviewerForm" class="btn btn-success">
                                    {{ showReviewerForm ? '폼 닫기' : '+ 새 리뷰어 추가' }}
                                </button>
                            </div>

                            <!-- 리뷰어 추가 폼 -->
                            <div v-if="showReviewerForm" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                                <h4 style="margin-bottom: 15px;">새 리뷰어 계정 생성</h4>
                                <div class="form-row">
                                    <div>
                                        <label style="font-weight: 600;">소속 고객사 *</label>
                                        <select v-model="reviewerForm.company_id" class="input" required>
                                            <option value="">고객사 선택</option>
                                            <option v-for="company in allCompanies" :key="company.id" :value="company.id">
                                                {{ company.display_name }}
                                            </option>
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-weight: 600;">사용자명 *</label>
                                        <input v-model="reviewerForm.username" type="text" class="input" placeholder="reviewer1">
                                    </div>
                                </div>
                                <div class="form-row">
                                    <div>
                                        <label style="font-weight: 600;">비밀번호 *</label>
                                        <input v-model="reviewerForm.password" type="password" class="input" placeholder="비밀번호">
                                    </div>
                                    <div>
                                        <label style="font-weight: 600;">이름</label>
                                        <input v-model="reviewerForm.full_name" type="text" class="input" placeholder="홍길동">
                                    </div>
                                </div>
                                <div style="display: flex; gap: 10px; margin-top: 15px;">
                                    <button @click="createReviewer" class="btn btn-success" style="flex: 1;">리뷰어 생성</button>
                                    <button @click="resetReviewerForm" class="btn btn-secondary">초기화</button>
                                    <button @click="showReviewerForm = false" class="btn btn-secondary">취소</button>
                                </div>
                            </div>

                            <!-- 리뷰어 목록 -->
                            <div style="overflow-x: auto;">
                                <table class="sheet-table">
                                    <thead>
                                        <tr>
                                            <th>사용자명</th>
                                            <th>이름</th>
                                            <th>소속 고객사</th>
                                            <th>역할</th>
                                            <th>배정된 업체</th>
                                            <th>등록 리뷰</th>
                                            <th>생성일</th>
                                            <th>작업</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="user in allUsers" :key="user.id">
                                            <td style="font-weight: 600;">{{ user.username }}</td>
                                            <td>{{ user.full_name || '-' }}</td>
                                            <td>{{ user.company_name }}</td>
                                            <td>
                                                <span :class="user.role === 'admin' ? 'status-failed' : 'status-completed'">
                                                    {{ user.role === 'admin' ? '관리자' : '리뷰어' }}
                                                </span>
                                            </td>
                                            <td style="font-size: 12px;">{{ getUserAssignedStores(user.id) }}</td>
                                            <td style="text-align: center;">{{ getUserReviewCount(user.id) }}개</td>
                                            <td style="font-size: 12px;">{{ formatDate(user.created_at) }}</td>
                                            <td>
                                                <button @click="manageUserStores(user)" class="btn btn-warning" style="font-size: 11px; padding: 4px 8px;">
                                                    🔗 배정 관리
                                                </button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- 대량 업로드 -->
                        <div v-if="adminTab === 'bulk'">
                            <h3 style="margin-bottom: 20px;">📊 엑셀 대량 업로드</h3>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 25px;">
                                <!-- 업체 대량 등록 -->
                                <div style="border: 2px solid #28a745; border-radius: 12px; padding: 20px;">
                                    <h4 style="color: #28a745; margin-bottom: 15px;">🏪 업체 대량 등록</h4>
                                    <p style="color: #666; font-size: 13px; margin-bottom: 15px;">
                                        Excel 파일로 여러 업체를 한 번에 등록
                                    </p>
                                    <input @change="handleStoreExcel" type="file" accept=".xlsx,.xls" class="input">
                                    <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 12px;">
                                        <p><strong>Excel 형식:</strong></p>
                                        <p>A: 고객사ID | B: 업체명 | C: 업종 | D: 위치 | E: 시작일 | F: 일일목표 | G: 기간</p>
                                    </div>
                                </div>
                                
                                <!-- 리뷰 대량 등록 -->
                                <div style="border: 2px solid #007bff; border-radius: 12px; padding: 20px;">
                                    <h4 style="color: #007bff; margin-bottom: 15px;">📝 리뷰 대량 등록</h4>
                                    <p style="color: #666; font-size: 13px; margin-bottom: 15px;">
                                        Excel 파일로 여러 리뷰 URL을 한 번에 등록
                                    </p>
                                    <input @change="handleReviewExcel" type="file" accept=".xlsx,.xls" class="input">
                                    <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 12px;">
                                        <p><strong>Excel 형식:</strong></p>
                                        <p>A: 업체명 | B: 리뷰URL</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 고객사 관리자 페이지 -->
                <div v-if="userType === 'company'">
                    <div class="card">
                        <div style="display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #eee; padding-bottom: 15px;">
                            <button @click="companyTab = 'dashboard'" :class="companyTab === 'dashboard' ? 'tab active' : 'tab'">
                                📊 대시보드
                            </button>
                            <button @click="companyTab = 'reviews'" :class="companyTab === 'reviews' ? 'tab active' : 'tab'">
                                📝 리뷰 관리
                            </button>
                            <button @click="companyTab = 'reports'" :class="companyTab === 'reports' ? 'tab active' : 'tab'">
                                📈 리포트
                            </button>
                        </div>

                        <!-- 고객사 대시보드 -->
                        <div v-if="companyTab === 'dashboard'">
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
                                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 12px; text-align: center;">
                                    <h4 style="margin-bottom: 10px;">🏪 관리 업체</h4>
                                    <p style="font-size: 2.5rem; font-weight: bold;">{{ myStores.length }}</p>
                                </div>
                                <div style="background: linear-gradient(135deg, #51cf66 0%, #48c78e 100%); color: white; padding: 20px; border-radius: 12px; text-align: center;">
                                    <h4 style="margin-bottom: 10px;">📝 총 리뷰</h4>
                                    <p style="font-size: 2.5rem; font-weight: bold;">{{ myReviews.length }}</p>
                                </div>
                                <div style="background: linear-gradient(135deg, #ffd93d 0%, #ff6b6b 100%); color: white; padding: 20px; border-radius: 12px; text-align: center;">
                                    <h4 style="margin-bottom: 10px;">⏳ 대기중</h4>
                                    <p style="font-size: 2.5rem; font-weight: bold;">{{ getMyPendingCount() }}</p>
                                </div>
                                <div style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; padding: 20px; border-radius: 12px; text-align: center;">
                                    <h4 style="margin-bottom: 10px;">✅ 완료</h4>
                                    <p style="font-size: 2.5rem; font-weight: bold;">{{ getMyCompletedCount() }}</p>
                                </div>
                            </div>

                            <!-- 업체별 현황 -->
                            <h4 style="margin-bottom: 15px;">🏪 업체별 현황</h4>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
                                <div v-for="store in myStores" :key="store.id" 
                                     style="border: 1px solid #ddd; border-radius: 10px; padding: 15px; background: white;">
                                    <h5 style="color: #333; margin-bottom: 8px;">{{ store.name }}</h5>
                                    <p style="font-size: 12px; color: #666; margin-bottom: 8px;">{{ store.category }} • {{ store.location }}</p>
                                    
                                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px;">
                                        <div style="text-align: center; padding: 8px; background: #e3f2fd; border-radius: 6px;">
                                            <p style="font-size: 14px; font-weight: bold; color: #1565c0;">{{ getStoreReviewCount(store.id) }}</p>
                                            <p style="font-size: 10px; color: #1976d2;">총 리뷰</p>
                                        </div>
                                        <div style="text-align: center; padding: 8px; background: #e8f5e8; border-radius: 6px;">
                                            <p style="font-size: 14px; font-weight: bold; color: #2e7d32;">{{ getStoreCompletedCount(store.id) }}</p>
                                            <p style="font-size: 10px; color: #388e3c;">완료</p>
                                        </div>
                                        <div style="text-align: center; padding: 8px; background: #fff3cd; border-radius: 6px;">
                                            <p style="font-size: 14px; font-weight: bold; color: #f57f17;">{{ getStorePendingCount(store.id) }}</p>
                                            <p style="font-size: 10px; color: #f9a825;">대기</p>
                                        </div>
                                    </div>
                                    
                                    <div style="display: flex; gap: 5px;">
                                        <button @click="viewStoreReviews(store)" class="btn btn-primary" style="flex: 1; font-size: 11px; padding: 6px;">
                                            📝 리뷰 보기
                                        </button>
                                        <button @click="exportStoreData(store)" class="btn btn-success" style="flex: 1; font-size: 11px; padding: 6px;">
                                            📊 엑셀 저장
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 리뷰 관리 -->
                        <div v-if="companyTab === 'reviews'">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                                <h3>📝 리뷰 관리 (구글시트 스타일)</h3>
                                <div style="display: flex; gap: 8px;">
                                    <button @click="showReviewForm = !showReviewForm" class="btn btn-primary">
                                        {{ showReviewForm ? '폼 닫기' : '+ 리뷰 추가' }}
                                    </button>
                                    <button @click="processAllPending" class="btn btn-success">
                                        🚀 전체 처리 ({{ getMyPendingCount() }}개)
                                    </button>
                                </div>
                            </div>

                            <!-- 리뷰 추가 폼 -->
                            <div v-if="showReviewForm" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                                <div class="form-row">
                                    <div>
                                        <label style="font-weight: 600;">업체 선택 *</label>
                                        <select v-model="reviewForm.store_id" class="input" required>
                                            <option value="">업체 선택</option>
                                            <option v-for="store in myStores" :key="store.id" :value="store.id">
                                                {{ store.name }} ({{ store.location }})
                                            </option>
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-weight: 600;">리뷰 URL *</label>
                                        <input v-model="reviewForm.review_url" type="url" class="input" required
                                               placeholder="https://naver.me/... 또는 https://m.place.naver.com/...">
                                    </div>
                                </div>
                                <div style="display: flex; gap: 10px; margin-top: 15px;">
                                    <button @click="addReview" class="btn btn-primary" style="flex: 1;">추가</button>
                                    <button @click="showReviewForm = false" class="btn btn-secondary">취소</button>
                                </div>
                            </div>

                            <!-- 구글시트 스타일 리뷰 테이블 -->
                            <div style="overflow-x: auto;">
                                <table class="sheet-table">
                                    <thead>
                                        <tr>
                                            <th style="width: 30px;">#</th>
                                            <th style="width: 120px;">A<br>업체명</th>
                                            <th style="width: 180px;">B<br>리뷰URL</th>
                                            <th style="min-width: 250px;">C<br>리뷰본문</th>
                                            <th style="width: 80px;">D<br>영수증날짜</th>
                                            <th style="width: 100px;">E<br>등록일</th>
                                            <th style="width: 70px;">F<br>상태</th>
                                            <th style="width: 80px;">작업</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="(review, index) in myReviews" :key="review.id">
                                            <td style="background: #f8f9fa; text-align: center; font-weight: 600;">{{ index + 1 }}</td>
                                            <td style="font-weight: 600;">{{ review.store_name }}</td>
                                            <td style="font-size: 11px;">
                                                <a :href="review.review_url" target="_blank" style="color: #1a73e8;">
                                                    {{ review.review_url.substring(0, 25) }}...
                                                </a>
                                            </td>
                                            <td style="font-size: 12px; max-height: 50px; overflow-y: auto;">
                                                {{ review.extracted_review_text || (review.status === 'pending' ? '추출 대기' : '-') }}
                                            </td>
                                            <td style="text-align: center; font-weight: 600;">
                                                {{ review.extracted_receipt_date || '-' }}
                                            </td>
                                            <td style="font-size: 11px;">{{ formatDate(review.created_at) }}</td>
                                            <td style="text-align: center;">
                                                <span :class="'status-' + review.status">{{ getStatusText(review.status) }}</span>
                                            </td>
                                            <td style="text-align: center;">
                                                <button v-if="review.status === 'pending'" @click="processReview(review.id)" 
                                                        style="background: #1a73e8; color: white; border: none; padding: 3px 6px; border-radius: 4px; font-size: 10px; cursor: pointer;">
                                                    ▶️
                                                </button>
                                                <button @click="viewDetail(review)" 
                                                        style="background: #34a853; color: white; border: none; padding: 3px 6px; border-radius: 4px; font-size: 10px; cursor: pointer;">
                                                    👁️
                                                </button>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 리뷰어 페이지 -->
                <div v-if="userType === 'reviewer'">
                    <div class="card">
                        <h3 style="margin-bottom: 20px;">📝 배정된 업체 리뷰 관리</h3>
                        
                        <!-- 배정된 업체 현황 -->
                        <div style="background: #e8f5e8; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                            <h4 style="color: #155724; margin-bottom: 15px;">🏪 내가 담당하는 업체들</h4>
                            <div v-if="myAssignedStores.length === 0" style="text-align: center; color: #666; padding: 20px;">
                                <p>배정된 업체가 없습니다</p>
                                <p style="font-size: 12px;">관리자에게 업체 배정을 요청하세요</p>
                            </div>
                            <div v-else style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                                <div v-for="store in myAssignedStores" :key="store.id" 
                                     style="border: 1px solid #c3e6cb; border-radius: 8px; padding: 15px; background: white;">
                                    <h5 style="margin-bottom: 8px;">{{ store.name }}</h5>
                                    <p style="font-size: 12px; color: #666; margin-bottom: 10px;">{{ store.location }} • {{ store.category }}</p>
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <span style="font-size: 12px; color: #155724;">📊 내 리뷰: {{ getMyStoreReviewCount(store.id) }}개</span>
                                        <button @click="addReviewForStore(store)" class="btn btn-success" style="font-size: 11px; padding: 5px 10px;">
                                            + 리뷰 추가
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 리뷰어 리뷰 추가 폼 -->
                        <div v-if="showReviewerReviewForm" style="background: #e3f2fd; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                            <h4 style="margin-bottom: 15px;">📝 {{ selectedStoreForReview?.name }} 리뷰 추가</h4>
                            <div>
                                <label style="font-weight: 600; margin-bottom: 8px; display: block;">네이버 리뷰 URL</label>
                                <input v-model="reviewerReviewForm.review_url" type="url" class="input" required
                                       placeholder="https://naver.me/... 또는 https://m.place.naver.com/my/review/...">
                            </div>
                            <div style="display: flex; gap: 10px; margin-top: 15px;">
                                <button @click="submitReviewerReview" class="btn btn-primary" style="flex: 1;">추가</button>
                                <button @click="showReviewerReviewForm = false" class="btn btn-secondary">취소</button>
                            </div>
                        </div>

                        <!-- 내 리뷰 목록 -->
                        <div style="overflow-x: auto;">
                            <table class="sheet-table">
                                <thead>
                                    <tr>
                                        <th>업체명</th>
                                        <th>리뷰URL</th>
                                        <th>리뷰본문</th>
                                        <th>영수증날짜</th>
                                        <th>등록일</th>
                                        <th>상태</th>
                                        <th>작업</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="review in myReviews" :key="review.id">
                                        <td style="font-weight: 600;">{{ review.store_name }}</td>
                                        <td style="font-size: 11px;">
                                            <a :href="review.review_url" target="_blank" style="color: #1a73e8;">
                                                {{ review.review_url.substring(0, 20) }}...
                                            </a>
                                        </td>
                                        <td style="font-size: 11px; max-height: 40px; overflow-y: auto;">
                                            {{ review.extracted_review_text || (review.status === 'pending' ? '추출 대기' : '-') }}
                                        </td>
                                        <td style="text-align: center; font-weight: 600;">
                                            {{ review.extracted_receipt_date || '-' }}
                                        </td>
                                        <td style="font-size: 11px;">{{ formatDate(review.created_at) }}</td>
                                        <td style="text-align: center;">
                                            <span :class="'status-' + review.status">{{ getStatusText(review.status) }}</span>
                                        </td>
                                        <td style="text-align: center;">
                                            <button v-if="review.status === 'pending'" @click="processReview(review.id)" 
                                                    style="background: #1a73e8; color: white; border: none; padding: 3px 6px; border-radius: 3px; font-size: 10px;">
                                                ▶️
                                            </button>
                                            <button @click="viewDetail(review)" 
                                                    style="background: #34a853; color: white; border: none; padding: 3px 6px; border-radius: 3px; font-size: 10px; margin-left: 2px;">
                                                👁️
                                            </button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 상세 모달 -->
        <div v-if="selectedDetail" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000;" @click="selectedDetail = null">
            <div style="background: white; border-radius: 15px; max-width: 700px; width: 90%; max-height: 85vh; overflow-y: auto;" @click.stop>
                <div style="background: #667eea; color: white; padding: 20px; border-radius: 15px 15px 0 0;">
                    <h3>{{ selectedDetail.title }}</h3>
                    <button @click="selectedDetail = null" style="position: absolute; top: 15px; right: 20px; background: none; border: none; color: white; font-size: 20px; cursor: pointer;">×</button>
                </div>
                <div style="padding: 25px;" v-html="selectedDetail.content"></div>
            </div>
        </div>
        
        <!-- 로딩 -->
        <div v-if="loading" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 2000;">
            <div style="background: white; padding: 30px; border-radius: 15px; text-align: center;">
                <div style="width: 40px; height: 40px; border: 3px solid #f3f3f3; border-top: 3px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px;"></div>
                <p style="font-weight: 600;">{{ loadingMessage }}</p>
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
                    isLoggedIn: false,
                    userType: null, // 'super', 'company', 'reviewer'
                    currentUser: {},
                    
                    loginMode: 'super', // 'super', 'company', 'reviewer'
                    selectedCompanyId: '',
                    loginForm: { username: 'superadmin', password: 'superadmin123' },
                    
                    loading: false,
                    loadingMessage: '처리 중...',
                    
                    // 탭 상태
                    adminTab: 'companies',
                    companyTab: 'dashboard',
                    
                    // 데이터
                    companies: [],
                    allCompanies: [],
                    allStores: [],
                    allUsers: [],
                    allReviews: [],
                    myStores: [],
                    myReviews: [],
                    myAssignedStores: [],
                    
                    // 폼 상태
                    showCompanyForm: false,
                    showStoreForm: false,
                    showReviewerForm: false,
                    showReviewForm: false,
                    showReviewerReviewForm: false,
                    
                    // 폼 데이터
                    companyForm: {
                        name: '', display_name: '', contact_email: '', contact_phone: '',
                        admin_username: '', admin_password: ''
                    },
                    storeForm: {
                        company_id: '', name: '', category: '', location: '', description: '',
                        campaign_start_date: '', daily_target_count: 1, campaign_duration_days: 30
                    },
                    reviewerForm: {
                        company_id: '', username: '', password: '', full_name: ''
                    },
                    reviewForm: {
                        store_id: '', review_url: ''
                    },
                    reviewerReviewForm: {
                        review_url: ''
                    },
                    
                    selectedDetail: null,
                    selectedStoreForReview: null
                }
            },
            
            async mounted() {
                await this.loadCompanies();
            },
            
            methods: {
                async loadCompanies() {
                    try {
                        const response = await axios.get('/api/companies');
                        this.companies = response.data;
                        this.allCompanies = response.data;
                    } catch (error) {
                        console.error('고객사 로드 실패:', error);
                    }
                },
                
                async login() {
                    this.loading = true;
                    this.loadingMessage = '로그인 중...';
                    
                    try {
                        let endpoint = '/auth/login-super';
                        let data = {
                            username: this.loginForm.username,
                            password: this.loginForm.password
                        };
                        
                        if (this.loginMode !== 'super') {
                            endpoint = '/auth/login';
                            data.company_id = this.selectedCompanyId;
                            data.user_type = this.loginMode;
                        }
                        
                        const response = await axios.post(endpoint, data);
                        this.currentUser = response.data;
                        this.userType = response.data.type;
                        this.isLoggedIn = true;
                        
                        // 사용자 타입별 데이터 로드
                        if (this.userType === 'super') {
                            await this.loadAdminData();
                        } else if (this.userType === 'company') {
                            await this.loadCompanyData();
                        } else {
                            await this.loadReviewerData();
                        }
                        
                        alert(`✅ ${this.userType === 'super' ? '시스템 관리자' : this.userType === 'company' ? '고객사 관리자' : '리뷰어'}로 로그인되었습니다!`);
                        
                    } catch (error) {
                        alert('❌ 로그인 실패: ' + (error.response?.data?.detail || '계정 정보를 확인해주세요'));
                    } finally {
                        this.loading = false;
                    }
                },
                
                logout() {
                    this.isLoggedIn = false;
                    this.userType = null;
                    this.currentUser = {};
                    this.loginMode = 'super';
                    this.selectedCompanyId = '';
                    this.loginForm = { username: 'superadmin', password: 'superadmin123' };
                },
                
                async loadAdminData() {
                    // 시스템 관리자 데이터 로드
                    await Promise.all([
                        this.loadAllCompanies(),
                        this.loadAllStores(), 
                        this.loadAllUsers(),
                        this.loadAllReviews()
                    ]);
                },
                
                async loadCompanyData() {
                    // 고객사 관리자 데이터 로드
                    await Promise.all([
                        this.loadMyStores(),
                        this.loadMyReviews()
                    ]);
                },
                
                async loadReviewerData() {
                    // 리뷰어 데이터 로드
                    await Promise.all([
                        this.loadMyAssignedStores(),
                        this.loadMyReviews()
                    ]);
                },
                
                async loadAllCompanies() {
                    try {
                        const response = await axios.get('/api/admin/companies');
                        this.allCompanies = response.data;
                    } catch (error) {
                        console.error('전체 고객사 로드 실패:', error);
                    }
                },
                
                async loadAllStores() {
                    try {
                        const response = await axios.get('/api/admin/stores');
                        this.allStores = response.data;
                    } catch (error) {
                        console.error('전체 업체 로드 실패:', error);
                    }
                },
                
                async loadMyStores() {
                    try {
                        const response = await axios.get(`/api/company/${this.currentUser.company_id}/stores`);
                        this.myStores = response.data;
                    } catch (error) {
                        console.error('내 업체 로드 실패:', error);
                    }
                },
                
                async loadMyReviews() {
                    try {
                        const endpoint = this.userType === 'company' ? 
                                        `/api/company/${this.currentUser.company_id}/reviews` :
                                        `/api/reviewer/${this.currentUser.id}/reviews`;
                        const response = await axios.get(endpoint);
                        this.myReviews = response.data;
                    } catch (error) {
                        console.error('내 리뷰 로드 실패:', error);
                    }
                },
                
                async createCompany() {
                    if (!this.companyForm.name || !this.companyForm.display_name || !this.companyForm.admin_username || !this.companyForm.admin_password) {
                        alert('❌ 필수 항목을 모두 입력해주세요');
                        return;
                    }
                    
                    this.loading = true;
                    this.loadingMessage = '고객사 생성 중...';
                    
                    try {
                        await axios.post('/api/admin/create-company', this.companyForm);
                        alert('✅ 고객사가 생성되었습니다!');
                        this.resetCompanyForm();
                        this.showCompanyForm = false;
                        await this.loadAdminData();
                    } catch (error) {
                        alert('❌ 생성 실패: ' + (error.response?.data?.detail || '알 수 없는 오류'));
                    } finally {
                        this.loading = false;
                    }
                },
                
                async createStore() {
                    if (!this.storeForm.company_id || !this.storeForm.name) {
                        alert('❌ 고객사와 업체명을 입력해주세요');
                        return;
                    }
                    
                    this.loading = true;
                    this.loadingMessage = '업체 등록 중...';
                    
                    try {
                        await axios.post('/api/admin/create-store', this.storeForm);
                        alert('✅ 업체가 등록되었습니다!');
                        this.resetStoreForm();
                        this.showStoreForm = false;
                        await this.loadAllStores();
                    } catch (error) {
                        alert('❌ 등록 실패: ' + (error.response?.data?.detail || '알 수 없는 오류'));
                    } finally {
                        this.loading = false;
                    }
                },
                
                async addReview() {
                    if (!this.reviewForm.store_id || !this.reviewForm.review_url) {
                        alert('❌ 업체와 URL을 모두 입력해주세요');
                        return;
                    }
                    
                    const store = this.myStores.find(s => s.id == this.reviewForm.store_id);
                    
                    try {
                        await axios.post('/api/add-review', {
                            store_name: store.name,
                            store_id: this.reviewForm.store_id,
                            review_url: this.reviewForm.review_url,
                            company_id: this.currentUser.company_id
                        });
                        
                        alert('✅ 리뷰가 추가되었습니다!');
                        this.reviewForm = { store_id: '', review_url: '' };
                        this.showReviewForm = false;
                        await this.loadMyReviews();
                    } catch (error) {
                        alert('❌ 추가 실패: ' + error.message);
                    }
                },
                
                async processReview(reviewId) {
                    const review = this.myReviews.find(r => r.id === reviewId);
                    if (!confirm(`🚀 실제 네이버 리뷰 추출을 시작하시겠습니까?\\n\\n업체: ${review.store_name}`)) return;
                    
                    this.loading = true;
                    this.loadingMessage = `🔍 "${review.store_name}" 추출 중...`;
                    
                    try {
                        await axios.post(`/api/process-review/${reviewId}`);
                        alert('🚀 실제 추출 시작! 30초 후 결과 확인하세요.');
                        
                        setTimeout(async () => {
                            await this.loadMyReviews();
                            this.loading = false;
                        }, 30000);
                        
                    } catch (error) {
                        alert('❌ 처리 실패: ' + error.message);
                        this.loading = false;
                    }
                },
                
                addReviewForStore(store) {
                    this.selectedStoreForReview = store;
                    this.showReviewerReviewForm = true;
                },
                
                async submitReviewerReview() {
                    try {
                        await axios.post('/api/add-review', {
                            store_name: this.selectedStoreForReview.name,
                            store_id: this.selectedStoreForReview.id,
                            review_url: this.reviewerReviewForm.review_url,
                            company_id: this.currentUser.company_id
                        });
                        
                        alert('✅ 리뷰가 추가되었습니다!');
                        this.reviewerReviewForm = { review_url: '' };
                        this.showReviewerReviewForm = false;
                        this.selectedStoreForReview = null;
                        await this.loadMyReviews();
                    } catch (error) {
                        alert('❌ 추가 실패: ' + error.message);
                    }
                },
                
                viewDetail(review) {
                    this.selectedDetail = {
                        title: `🔍 ${review.store_name} 리뷰 상세`,
                        content: `
                            <div style="display: grid; gap: 15px;">
                                <div><strong>업체명:</strong> ${review.store_name}</div>
                                <div><strong>URL:</strong> <a href="${review.review_url}" target="_blank">${review.review_url}</a></div>
                                ${review.extracted_review_text ? `<div style="background: #f0f8ff; padding: 15px; border-radius: 8px;"><strong>리뷰 내용:</strong><br>${review.extracted_review_text}</div>` : ''}
                                ${review.extracted_receipt_date ? `<div><strong>영수증 날짜:</strong> ${review.extracted_receipt_date}</div>` : ''}
                                <div><strong>등록일:</strong> ${this.formatDate(review.created_at)}</div>
                                <div><strong>상태:</strong> ${this.getStatusText(review.status)}</div>
                                ${review.error_message ? `<div style="background: #ffe6e6; padding: 15px; border-radius: 8px; color: #d32f2f;"><strong>오류:</strong> ${review.error_message}</div>` : ''}
                            </div>
                        `
                    };
                },
                
                resetCompanyForm() {
                    this.companyForm = {
                        name: '', display_name: '', contact_email: '', contact_phone: '',
                        admin_username: '', admin_password: ''
                    };
                },
                
                resetStoreForm() {
                    this.storeForm = {
                        company_id: '', name: '', category: '', location: '', description: '',
                        campaign_start_date: '', daily_target_count: 1, campaign_duration_days: 30
                    };
                },
                
                resetReviewerForm() {
                    this.reviewerForm = {
                        company_id: '', username: '', password: '', full_name: ''
                    };
                },
                
                getMyPendingCount() {
                    return this.myReviews.filter(r => r.status === 'pending').length;
                },
                
                getMyCompletedCount() {
                    return this.myReviews.filter(r => r.status === 'completed').length;
                },
                
                getStoreReviewCount(storeId) {
                    return this.myReviews.filter(r => r.store_id === storeId).length;
                },
                
                getStatusText(status) {
                    const map = {
                        'pending': '대기',
                        'processing': '처리중',
                        'completed': '완료',
                        'failed': '실패'
                    };
                    return map[status] || status;
                },
                
                formatDate(dateString) {
                    return new Date(dateString).toLocaleDateString('ko-KR');
                }
            }
        }).mount('#app');
    </script>
</body>
</html>""")

# API 엔드포인트들
@app.get("/api/companies")
async def get_companies():
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, display_name, contact_email FROM companies WHERE is_active = 1')
    companies = cursor.fetchall()
    conn.close()
    return [{"id": c[0], "name": c[1], "display_name": c[2], "contact_email": c[3]} for c in companies]

@app.post("/auth/login-super")
async def login_super(login_data: dict):
    """시스템 관리자 로그인"""
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(login_data["password"].encode()).hexdigest()
    cursor.execute('SELECT * FROM super_admin WHERE username = ? AND password_hash = ?', 
                  (login_data["username"], password_hash))
    admin = cursor.fetchone()
    conn.close()
    
    if not admin:
        raise HTTPException(status_code=401, detail="잘못된 관리자 계정")
    
    return {
        "id": admin[0],
        "username": admin[1],
        "full_name": admin[3],
        "type": "super"
    }

@app.post("/auth/login")
async def login_user(login_data: dict):
    """고객사 관리자/리뷰어 로그인"""
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(login_data["password"].encode()).hexdigest()
    
    cursor.execute('''
        SELECT u.id, u.username, u.full_name, u.role, u.company_id, c.display_name
        FROM users u 
        JOIN companies c ON u.company_id = c.id
        WHERE u.username = ? AND u.password_hash = ? AND u.company_id = ? AND u.is_active = 1
    ''', (login_data["username"], password_hash, login_data["company_id"]))
    
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="잘못된 계정 정보")
    
    user_type = "company" if user[3] == "admin" else "reviewer"
    
    return {
        "id": user[0],
        "username": user[1],
        "full_name": user[2],
        "role": user[3],
        "company_id": user[4],
        "company_name": user[5],
        "type": user_type
    }

@app.post("/api/admin/create-company")
async def create_company(company_data: dict):
    """새 고객사 및 관리자 계정 생성"""
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    
    try:
        # 고객사 생성
        cursor.execute('''
            INSERT INTO companies (name, display_name, contact_email, contact_phone)
            VALUES (?, ?, ?, ?)
        ''', (company_data["name"], company_data["display_name"], 
              company_data.get("contact_email"), company_data.get("contact_phone")))
        
        company_id = cursor.lastrowid
        
        # 관리자 계정 생성
        admin_hash = hashlib.sha256(company_data["admin_password"].encode()).hexdigest()
        cursor.execute('''
            INSERT INTO users (company_id, username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, 'admin')
        ''', (company_id, company_data["admin_username"], admin_hash, 
              f'{company_data["display_name"]} 관리자'))
        
        conn.commit()
        return {"success": True, "company_id": company_id}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/create-store")
async def create_store(store_data: dict):
    """새 업체 생성"""
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO stores (company_id, name, category, location, description,
                              campaign_start_date, daily_target_count, campaign_duration_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (store_data["company_id"], store_data["name"], store_data.get("category"),
              store_data.get("location"), store_data.get("description"),
              store_data.get("campaign_start_date"), store_data.get("daily_target_count", 1),
              store_data.get("campaign_duration_days", 30)))
        
        conn.commit()
        return {"success": True, "store_id": cursor.lastrowid}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/companies")
async def get_all_companies():
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies ORDER BY created_at DESC')
    companies = cursor.fetchall()
    conn.close()
    
    return [{
        "id": c[0], "name": c[1], "display_name": c[2], "contact_email": c[3],
        "contact_phone": c[4], "subscription_plan": c[5], "is_active": bool(c[6]),
        "created_at": c[7]
    } for c in companies]

@app.get("/api/admin/stores")  
async def get_all_stores():
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*, c.display_name as company_name
        FROM stores s
        JOIN companies c ON s.company_id = c.id
        ORDER BY s.created_at DESC
    ''')
    stores = cursor.fetchall()
    conn.close()
    
    return [{
        "id": s[0], "company_id": s[1], "name": s[2], "description": s[3],
        "location": s[4], "category": s[5], "naver_place_url": s[6],
        "campaign_start_date": s[7], "daily_target_count": s[8], "campaign_duration_days": s[9],
        "is_active": bool(s[10]), "created_at": s[11], "company_name": s[12]
    } for s in stores]

@app.get("/api/company/{company_id}/stores")
async def get_company_stores(company_id: int):
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM stores WHERE company_id = ? AND is_active = 1', (company_id,))
    stores = cursor.fetchall()
    conn.close()
    
    return [{
        "id": s[0], "name": s[2], "description": s[3], "location": s[4], 
        "category": s[5], "daily_target_count": s[8], "campaign_duration_days": s[9]
    } for s in stores]

@app.get("/api/company/{company_id}/reviews")
async def get_company_reviews(company_id: int):
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, s.name as store_name, u.full_name as registered_by_name
        FROM reviews r
        JOIN stores s ON r.store_id = s.id
        LEFT JOIN users u ON r.registered_by_user_id = u.id
        WHERE r.company_id = ?
        ORDER BY r.created_at DESC
    ''', (company_id,))
    reviews = cursor.fetchall()
    conn.close()
    
    return [{
        "id": r[0], "store_name": r[13], "review_url": r[5], "url_type": r[11],
        "extracted_review_text": r[6], "extracted_receipt_date": r[7], 
        "status": r[9], "error_message": r[12], "created_at": r[18],
        "registered_by_name": r[14], "store_id": r[2]
    } for r in reviews]

@app.post("/api/add-review")
async def add_review(review_data: dict):
    """리뷰 추가 (구글시트 방식)"""
    url_type = "direct" if "/my/review/" in review_data["review_url"] else "shortcut"
    registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO reviews (company_id, store_id, registered_by_user_id, store_name, 
                           review_url, url_type, registration_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (review_data.get("company_id", 1), review_data.get("store_id"), 1,
          review_data["store_name"], review_data["review_url"], url_type, registration_date))
    
    conn.commit()
    review_id = cursor.lastrowid
    conn.close()
    
    return {"success": True, "review_id": review_id}

@app.post("/api/process-review/{review_id}")
async def process_review_endpoint(review_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(extract_real_review, review_id)
    return {"success": True, "message": "실제 추출 시작"}

def extract_real_review(review_id: int):
    """실제 네이버 리뷰 추출"""
    conn = sqlite3.connect('complete_system.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT store_name, review_url, url_type FROM reviews WHERE id = ?', (review_id,))
        result = cursor.fetchone()
        if not result:
            return
        
        store_name, review_url, url_type = result
        
        # 처리중 상태 업데이트
        cursor.execute('UPDATE reviews SET status = ? WHERE id = ?', ('processing', review_id))
        conn.commit()
        
        print(f"🚀 실제 추출 시작: {store_name} - {review_url}")
        
        # 실제 Selenium 추출
        try:
            from selenium import webdriver
            from selenium.webdriver.support.ui import WebDriverWait  
            from bs4 import BeautifulSoup
            import time
            
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=options)
            driver.get(review_url)
            
            if url_type == "direct":
                # 직접 리뷰 링크
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                review_elem = soup.find('a', {'data-pui-click-code': 'reviewend.text'})
                extracted_text = review_elem.get_text(strip=True) if review_elem else "리뷰 본문을 찾을 수 없습니다"
                
                time_elem = soup.find('time', {'aria-hidden': 'true'})
                extracted_date = time_elem.get_text(strip=True) if time_elem else "영수증 날짜를 찾을 수 없습니다"
                
            else:
                # 단축 URL 처리
                if "naver.me" in review_url:
                    WebDriverWait(driver, 10).until(lambda d: d.current_url != review_url)
                
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                target_review = None
                
                # 업체명 매칭
                review_blocks = soup.find_all('div', class_='hahVh2')
                for block in review_blocks:
                    shop_elem = block.find('span', class_='pui__pv1E2a')
                    if shop_elem and shop_elem.text.strip() == store_name:
                        target_review = block
                        break
                
                if target_review:
                    review_div = target_review.find('div', class_='pui__vn15t2')
                    extracted_text = review_div.text.strip() if review_div else "리뷰 본문을 찾을 수 없습니다"
                    
                    time_elem = target_review.find('time', {'aria-hidden': 'true'})
                    extracted_date = time_elem.text.strip() if time_elem else "영수증 날짜를 찾을 수 없습니다"
                else:
                    extracted_text = f"업체명 '{store_name}'과 일치하는 리뷰를 찾을 수 없습니다"
                    extracted_date = "날짜 정보 없음"
            
            driver.quit()
            
            # 성공 여부 판단
            if "찾을 수 없습니다" not in extracted_text and len(extracted_text) > 10:
                status = 'completed'
                print(f"✅ 추출 성공: {store_name}")
            else:
                status = 'failed'
                print(f"❌ 추출 실패: {store_name}")
            
            # 결과 저장
            cursor.execute('''
                UPDATE reviews 
                SET status = ?, extracted_review_text = ?, extracted_receipt_date = ?, processed_at = ?
                WHERE id = ?
            ''', (status, extracted_text, extracted_date, datetime.now().isoformat(), review_id))
            
        except Exception as e:
            print(f"❌ 추출 오류: {e}")
            cursor.execute('UPDATE reviews SET status = ?, error_message = ? WHERE id = ?',
                          ('failed', f"추출 오류: {str(e)}", review_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ 전체 오류: {e}")

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "complete-naver-review-system",
        "version": "4.0.0",
        "features": [
            "multi_company_management",
            "real_naver_extraction", 
            "excel_bulk_upload",
            "individual_reports",
            "campaign_management"
        ]
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print("네이버 리뷰 관리 시스템 - 완전 기능 버전!")
    print("시스템 관리자: superadmin / superadmin123")
    print(f"접속: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)