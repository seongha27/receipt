from fastapi import FastAPI, Form, BackgroundTasks, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse, StreamingResponse
import uvicorn
import sqlite3
import hashlib
import os
import re
import pandas as pd
import io
from datetime import datetime, timedelta
import tempfile
import zipfile
from typing import List, Optional
from werkzeug.utils import secure_filename

# 영수증생성기 모듈 import (안정성 우선 - 기존 방식)
from receipt_generator_module import (
    create_receipts_zip, smart_filter_menu, create_receipt_image_full
)
from receipt_generator_fixed import (
    parse_menu_input
)
from naver_scraper_full import get_naver_place_menu, format_menu_for_textarea
from excel_parser import parse_excel_file
from utils import remove_image_metadata, parse_text_to_files, allowed_file

app = FastAPI()

def get_db_path():
    """데이터베이스 절대 경로 반환"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clean.db')

def backup_database():
    """데이터베이스 백업 생성"""
    db_path = get_db_path()
    if os.path.exists(db_path):
        backup_path = os.path.join(os.path.dirname(db_path), f'backup_clean_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"데이터베이스 백업 생성: {backup_path}")
        return backup_path
    return None

def check_data_integrity():
    """데이터 무결성 체크"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # 각 테이블 레코드 수 확인
        cursor.execute('SELECT COUNT(*) FROM users')
        users_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM stores')
        stores_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM reviews')
        reviews_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"데이터 무결성 체크:")
        print(f"  사용자: {users_count}개")
        print(f"  업체: {stores_count}개") 
        print(f"  리뷰: {reviews_count}개")
        
        return True
    except Exception as e:
        print(f"데이터 무결성 체크 실패: {e}")
        return False

def init_db():
    """데이터베이스 초기화 (기존 데이터 완전 보존)"""
    db_path = get_db_path()
    
    # 기존 파일 존재 확인
    if os.path.exists(db_path):
        print(f"기존 데이터베이스 발견: {db_path} (크기: {os.path.getsize(db_path)} bytes)")
        print("기존 데이터를 보존합니다.")
    else:
        print(f"새 데이터베이스 생성: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 테이블이 없을 때만 생성 (IF NOT EXISTS 사용)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        user_type TEXT,
        company_name TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY,
        company_name TEXT,
        name TEXT,
        start_date TEXT,
        daily_count INTEGER,
        duration_days INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY,
        reviewer_username TEXT,
        store_id INTEGER
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY,
        store_name TEXT,
        review_url TEXT,
        extracted_text TEXT,
        extracted_date TEXT,
        status TEXT DEFAULT 'pending',
        registered_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 관리자 계정이 없을 때만 생성
    cursor.execute('SELECT COUNT(*) FROM users WHERE username = "admin"')
    admin_exists = cursor.fetchone()[0]
    
    if admin_exists == 0:
        admin_hash = hashlib.sha256("doemtmzpcl1!".encode()).hexdigest()
        cursor.execute('INSERT INTO users (username, password_hash, user_type) VALUES (?, ?, ?)', ('admin', admin_hash, 'admin'))
        print("관리자 계정 생성됨")
    else:
        print("기존 관리자 계정 유지")
    
    conn.commit()
    conn.close()
    print("데이터베이스 초기화 완료 (기존 데이터 보존)")

# 시스템 시작시 안전 절차
backup_database()  # 백업 생성
init_db()         # 데이터베이스 초기화 (기존 데이터 보존)
check_data_integrity()  # 데이터 무결성 체크

@app.get("/")
def home():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>네이버 리뷰 관리 시스템</title>
</head>
<body style="font-family: Arial; background: linear-gradient(135deg, #4285f4, #34a853); margin: 0; padding: 20px; min-height: 100vh;">
    <div style="max-width: 500px; margin: 100px auto;">
        <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); text-align: center;">
            <h1 style="margin-bottom: 30px; color: #333;">리뷰 관리 시스템</h1>
            
            <form action="/login" method="post">
                <div style="margin-bottom: 25px;">
                    <input name="username" type="text" placeholder="사용자명 (admin, adsketch, 홍길동)" 
                           style="width: 100%; padding: 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; margin-bottom: 15px;">
                    <input name="password" type="password" placeholder="비밀번호" 
                           style="width: 100%; padding: 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px;">
                </div>
                
                <button type="submit" style="width: 100%; padding: 15px; background: #4285f4; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 18px; font-weight: 600;">로그인</button>
            </form>
            
            <div style="margin-top: 25px; padding: 20px; background: #f8f9fa; border-radius: 10px; text-align: center;">
                <p style="margin: 0; color: #666; font-size: 14px;">관리자가 먼저 고객사와 리뷰어 계정을 생성해주세요</p>
            </div>
        </div>
    </div>
</body>
</html>""")

@app.post("/login")
async def login(username: str = Form(), password: str = Form()):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password_hash = ?', (username, password_hash))
    user = cursor.fetchone()
    
    if user:
        user_type = user[3]  # user_type 컬럼
        conn.close()
        
        if user_type == 'admin':
            return RedirectResponse(url="/admin", status_code=302)
        elif user_type == 'company':
            return RedirectResponse(url=f"/company/{username}", status_code=302)
        elif user_type == 'reviewer':
            return RedirectResponse(url=f"/reviewer/{username}", status_code=302)
    
    conn.close()
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>로그인 실패</title></head>
<body style="font-family: Arial; background: #f0f0f0; text-align: center; padding: 50px;">
    <div style="background: white; padding: 30px; border-radius: 10px; max-width: 400px; margin: 0 auto;">
        <h2 style="color: #dc3545;">로그인 실패</h2>
        <p>사용자명 또는 비밀번호가 올바르지 않습니다.</p>
        <a href="/" style="padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">다시 시도</a>
    </div>
</body>
</html>""")

@app.get("/admin")
def admin_page():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 고객사 목록
    cursor.execute('SELECT * FROM users WHERE user_type = "company"')
    companies = cursor.fetchall()
    
    # 업체 목록
    cursor.execute('SELECT * FROM stores ORDER BY created_at DESC')
    stores = cursor.fetchall()
    
    # 리뷰어 목록
    cursor.execute('SELECT * FROM users WHERE user_type = "reviewer"')
    reviewers = cursor.fetchall()
    
    # 배정 목록
    cursor.execute('''
        SELECT a.id, a.reviewer_username, s.name as store_name, s.company_name
        FROM assignments a
        LEFT JOIN stores s ON a.store_id = s.id
    ''')
    assignments = cursor.fetchall()
    
    # 리뷰 목록
    cursor.execute('SELECT * FROM reviews ORDER BY created_at DESC')
    reviews = cursor.fetchall()
    
    conn.close()
    
    # HTML 데이터 생성
    companies_html = ''.join([f'<div style="padding: 12px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;"><strong>{c[1]}</strong><span style="color: #666; font-size: 12px;">{c[4] or c[1]}</span></div>' for c in companies]) or '<p style="color: #999; text-align: center; padding: 20px;">등록된 고객사가 없습니다</p>'
    
    companies_options = ''.join([f'<option value="{c[4] or c[1]}">{c[4] or c[1]}</option>' for c in companies])
    
    stores_html = ''
    for s in stores:
        # 종료일 계산
        end_date = ''
        if s[3]:  # start_date
            try:
                start = datetime.strptime(s[3], '%Y-%m-%d')
                end = start + timedelta(days=(s[5] or 30))
                end_date = end.strftime('%Y-%m-%d')
            except:
                end_date = ''
        
        stores_html += f'''<div style="padding: 12px; border-bottom: 1px solid #eee;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong style="color: #333;">{s[2]}</strong>
                    <span style="margin-left: 10px; padding: 3px 8px; background: #e3f2fd; color: #1565c0; border-radius: 10px; font-size: 11px;">{s[1]}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="text-align: right; font-size: 12px; color: #666;">
                        목표: {(s[4] or 1) * (s[5] or 30)}개<br>
                        {s[3]} ~ {end_date}
                    </div>
                    <a href="/extend-store-admin/{s[1]}/{s[2]}" style="padding: 4px 8px; background: #ffc107; color: #333; text-decoration: none; border-radius: 3px; font-size: 11px; margin-right: 5px;">🔄 연장</a>
                    <a href="/delete-store/{s[0]}" onclick="return confirm('업체를 삭제하시겠습니까? 관련 배정과 리뷰도 함께 삭제됩니다.')" style="padding: 4px 8px; background: #dc3545; color: white; text-decoration: none; border-radius: 3px; font-size: 11px;">🗑️</a>
                </div>
            </div>
        </div>'''
    
    if not stores_html:
        stores_html = '<p style="color: #999; text-align: center; padding: 20px;">등록된 업체가 없습니다</p>'
    
    reviewers_html = ''.join([f'<div style="padding: 12px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;"><strong>{r[1]}</strong><a href="/delete-user/{r[1]}" onclick="return confirm(\'{r[1]} 리뷰어를 삭제하시겠습니까?\')" style="padding: 4px 8px; background: #dc3545; color: white; text-decoration: none; border-radius: 3px; font-size: 11px;">🗑️</a></div>' for r in reviewers]) or '<p style="color: #999; text-align: center; padding: 20px;">등록된 리뷰어가 없습니다</p>'
    
    reviewers_options = ''.join([f'<option value="{r[1]}">{r[1]}</option>' for r in reviewers])
    stores_options = ''.join([f'<option value="{s[0]}">{s[2]} ({s[1]})</option>' for s in stores])
    
    assignments_html = ''.join([f'<div style="padding: 12px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;"><span><strong>{a[1]}</strong> → {a[2]}</span><span style="color: #666; font-size: 12px;">{a[3]}</span></div>' for a in assignments]) or '<p style="color: #999; text-align: center; padding: 20px;">배정된 항목이 없습니다</p>'
    
    reviews_html = ''
    for r in reviews:
        status_color = '#28a745' if r[5] == 'completed' else '#ffc107' if r[5] == 'pending' else '#dc3545'
        status_text = '완료' if r[5] == 'completed' else '대기' if r[5] == 'pending' else '실패'
        process_button = f'<a href="/process-review/{r[0]}" style="padding: 4px 8px; background: #007bff; color: white; text-decoration: none; border-radius: 3px; font-size: 11px;">▶️ 추출</a>' if r[5] == "pending" else ""
        
        # 추출된 내용 미리보기
        extracted_preview = ""
        if r[3]:  # extracted_text가 있으면
            preview_text = r[3][:50] + "..." if len(r[3]) > 50 else r[3]
            extracted_preview = f'<div style="margin-top: 5px; padding: 8px; background: #e8f5e8; border-radius: 4px; font-size: 11px; color: #155724;"><strong>추출 내용:</strong> {preview_text}</div>'
        
        date_info = f'<span style="margin-left: 10px; color: #dc3545; font-weight: 600; font-size: 12px;">📅 {r[4]}</span>' if r[4] else ""
        
        # 버튼 처리
        action_buttons = ""
        if r[5] == "pending":
            action_buttons = f'<a href="/process-review/{r[0]}" style="padding: 4px 8px; background: #007bff; color: white; text-decoration: none; border-radius: 3px; font-size: 11px;">▶️ 추출</a>'
        elif r[5] == "failed":
            action_buttons = f'<a href="/retry-review/{r[0]}" style="padding: 4px 8px; background: #ffc107; color: #333; text-decoration: none; border-radius: 3px; font-size: 11px;">🔄 재시도</a>'
        
        # 리뷰 URL 표시
        url_info = f'<div style="margin-top: 5px; color: #666; font-size: 11px;"><strong>URL:</strong> <a href="{r[2]}" target="_blank" style="color: #007bff;">{r[2][:60]}...</a></div>' if r[2] else ""
        
        reviews_html += f'''<div style="padding: 12px; border-bottom: 1px solid #eee;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                <div>
                    <strong>{r[1]}</strong>
                    <span style="margin-left: 10px; padding: 2px 6px; background: {status_color}; color: white; border-radius: 8px; font-size: 10px;">{status_text}</span>
                    <span style="margin-left: 10px; color: #666; font-size: 12px;">{r[6]}</span>
                    {date_info}
                </div>
                <div style="display: flex; gap: 5px;">
                    {action_buttons}
                    <a href="/delete-review/{r[0]}" onclick="return confirm('이 리뷰를 삭제하시겠습니까?')" style="padding: 4px 8px; background: #dc3545; color: white; text-decoration: none; border-radius: 3px; font-size: 11px;">🗑️</a>
                </div>
            </div>
            {url_info}
            {extracted_preview}
        </div>'''
    
    if not reviews_html:
        reviews_html = '<p style="color: #999; text-align: center; padding: 20px;">등록된 리뷰가 없습니다</p>'
    
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>시스템 관리자</title>
    <script>
        function showTab(tab) {{
            // 모든 탭 숨기기
            const tabs = ['companies', 'stores', 'reviewers', 'assignments', 'reviews', 'upload', 'receipt'];
            tabs.forEach(t => {{
                const tabElement = document.getElementById(t + 'Tab');
                const btnElement = document.getElementById(t + 'Btn');
                
                if (tabElement) {{
                    tabElement.style.display = t === tab ? 'block' : 'none';
                }}
                
                if (btnElement) {{
                    btnElement.style.background = t === tab ? '#4285f4' : '#f8f9fa';
                    btnElement.style.color = t === tab ? 'white' : '#333';
                }}
            }});
        }}
        
        // 페이지 로드시 탭 복원
        window.onload = function() {{
            const urlParams = new URLSearchParams(window.location.search);
            const activeTab = urlParams.get('tab') || 'companies';
            showTab(activeTab);
        }};
        
        // 탭 클릭시 URL 업데이트
        function showTabWithUrl(tab) {{
            showTab(tab);
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('tab', tab);
            window.history.pushState({{}}, '', newUrl);
        }}
    </script>
</head>
<body style="font-family: Arial; background: #f5f7fa; margin: 0; padding: 20px;">
    <div style="max-width: 1200px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #4285f4, #34a853); color: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; text-align: center;">
            <h1 style="margin: 0 0 10px 0; font-size: 2.2rem;">👑 시스템 관리자</h1>
            <p style="margin: 0; opacity: 0.9;">전체 시스템 관리 및 리뷰 추출 권한</p>
            <a href="/" style="margin-top: 15px; display: inline-block; color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px;">로그아웃</a>
        </div>
        
        <div style="background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px;">
            <!-- 탭 메뉴 -->
            <div style="margin-bottom: 25px; border-bottom: 2px solid #f0f0f0; padding-bottom: 15px;">
                <button onclick="showTabWithUrl('companies')" id="companiesBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #4285f4; color: white; cursor: pointer; font-weight: 600;">🏢 고객사</button>
                <button onclick="showTabWithUrl('stores')" id="storesBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">🏪 업체</button>
                <button onclick="showTabWithUrl('reviewers')" id="reviewersBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">👤 리뷰어</button>
                <button onclick="showTabWithUrl('assignments')" id="assignmentsBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">🔗 배정</button>
                <button onclick="showTabWithUrl('reviews')" id="reviewsBtn" style="padding: 12px 24px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">📝 리뷰</button>
                <button onclick="showTabWithUrl('upload')" id="uploadBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">📊 엑셀업로드</button>
                <button onclick="showTabWithUrl('receipt')" id="receiptBtn" style="padding: 12px 24px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">🧾 영수증생성</button>
            </div>

            <!-- 고객사 관리 -->
            <div id="companiesTab">
                <h3 style="margin-bottom: 20px; color: #333;">🏢 고객사 계정 관리</h3>
                <form action="/create-company" method="post" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 15px; align-items: center;">
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">고객사명 (ID로 사용)</label>
                            <input name="name" placeholder="예: studioview" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">비밀번호</label>
                            <input name="password" type="password" placeholder="비밀번호 설정" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                        </div>
                        <button type="submit" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">생성</button>
                    </div>
                </form>
                
                <div style="background: #ffffff; border: 1px solid #e9ecef; border-radius: 10px; padding: 15px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">등록된 고객사 목록</h4>
                    {companies_html}
                </div>
            </div>

            <!-- 업체 관리 -->
            <div id="storesTab" style="display: none;">
                <h3 style="margin-bottom: 20px; color: #333;">🏪 업체 등록 및 관리</h3>
                <form action="/create-store" method="post" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 20px; margin-bottom: 15px;">
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">소속 고객사</label>
                            <select name="company_name" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                                <option value="">고객사 선택</option>
                                {companies_options}
                            </select>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">업체명 (정확한 네이버 업체명)</label>
                            <input name="name" placeholder="예: 스타벅스 강남점" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 15px; align-items: end;">
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">시작일</label>
                            <input name="start_date" type="date" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;">
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">하루 작업 갯수</label>
                            <input name="daily_count" type="number" value="1" min="1" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;">
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">캠페인 일수</label>
                            <input name="duration_days" type="number" value="30" min="1" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;">
                        </div>
                        <button type="submit" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">등록</button>
                    </div>
                </form>
                
                <div style="background: #ffffff; border: 1px solid #e9ecef; border-radius: 10px; padding: 15px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">등록된 업체 목록</h4>
                    {stores_html}
                </div>
            </div>

            <!-- 리뷰어 관리 -->
            <div id="reviewersTab" style="display: none;">
                <h3 style="margin-bottom: 20px; color: #333;">👤 리뷰어 계정 관리</h3>
                <form action="/create-reviewer" method="post" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 15px; align-items: center;">
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">리뷰어명 (ID로 사용)</label>
                            <input name="name" placeholder="예: 김리뷰" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">비밀번호</label>
                            <input name="password" type="password" placeholder="비밀번호 설정" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                        </div>
                        <button type="submit" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">생성</button>
                    </div>
                </form>
                
                <div style="background: #ffffff; border: 1px solid #e9ecef; border-radius: 10px; padding: 15px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">등록된 리뷰어 목록</h4>
                    {reviewers_html}
                </div>
            </div>

            <!-- 배정 관리 -->
            <div id="assignmentsTab" style="display: none;">
                <h3 style="margin-bottom: 20px; color: #333;">🔗 리뷰어-업체 배정</h3>
                <form action="/create-assignment" method="post" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 15px; align-items: center;">
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">리뷰어 선택</label>
                            <select name="reviewer_username" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                                <option value="">리뷰어 선택</option>
                                {reviewers_options}
                            </select>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">업체 선택</label>
                            <select name="store_id" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                                <option value="">업체 선택</option>
                                {stores_options}
                            </select>
                        </div>
                        <button type="submit" style="padding: 10px 20px; background: #ffc107; color: #333; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">배정</button>
                    </div>
                </form>
                
                <div style="background: #ffffff; border: 1px solid #e9ecef; border-radius: 10px; padding: 15px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">현재 배정 현황</h4>
                    {assignments_html}
                </div>
            </div>

            <!-- 리뷰 관리 -->
            <div id="reviewsTab" style="display: none;">
                <h3 style="margin-bottom: 20px; color: #333;">📝 리뷰 관리 (추출 권한)</h3>
                <form action="/add-review" method="post" style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div style="display: grid; grid-template-columns: 1fr 2fr auto; gap: 15px; align-items: center;">
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">업체 선택</label>
                            <select name="store_id" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                                <option value="">업체 선택</option>
                                {stores_options}
                            </select>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">네이버 리뷰 URL</label>
                            <input name="review_url" type="url" placeholder="https://naver.me/... 또는 https://m.place.naver.com/..." style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px;" required>
                        </div>
                        <button type="submit" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">등록</button>
                    </div>
                </form>
                
                <div style="margin-bottom: 20px; text-align: center;">
                    <a href="/process-all" style="padding: 12px 30px; background: #28a745; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">🚀 전체 리뷰 일괄 처리</a>
                </div>
                
                <div style="background: #ffffff; border: 1px solid #e9ecef; border-radius: 10px; padding: 15px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">전체 리뷰 목록</h4>
                    {reviews_html}
                </div>
            </div>

            <!-- 엑셀 업로드 -->
            <div id="uploadTab" style="display: none;">
                <h3 style="margin-bottom: 20px; color: #333;">📊 엑셀 대량 업로드</h3>
                
                <!-- 업체 대량 등록 -->
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 25px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">🏪 업체 대량 등록</h4>
                    <form action="/upload-stores" method="post" enctype="multipart/form-data">
                        <div style="margin-bottom: 15px;">
                            <input type="file" name="excel_file" accept=".xlsx,.xls,.csv" style="margin-bottom: 10px; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                            <button type="submit" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">업체 일괄 등록</button>
                        </div>
                        <div style="background: #e8f5e8; padding: 15px; border-radius: 6px;">
                            <p style="margin: 0 0 10px 0; font-weight: 600; color: #155724;">📋 엑셀 형식 (A, B, C, D, E 순서):</p>
                            <p style="margin: 5px 0; color: #155724;">A열: 고객사명 | B열: 업체명 | C열: 시작일(YYYY-MM-DD) | D열: 하루갯수 | E열: 캠페인일수</p>
                        </div>
                    </form>
                    
                    <div style="margin-top: 15px; text-align: center;">
                        <a href="/download-template/stores" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; font-size: 12px;">📄 업체 템플릿 다운로드</a>
                    </div>
                </div>

                <!-- 리뷰 대량 등록 -->
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 25px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">📝 리뷰 대량 등록</h4>
                    <form action="/upload-reviews" method="post" enctype="multipart/form-data">
                        <div style="margin-bottom: 15px;">
                            <input type="file" name="excel_file" accept=".xlsx,.xls,.csv" style="margin-bottom: 10px; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                            <button type="submit" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">리뷰 일괄 등록</button>
                        </div>
                        <div style="background: #e3f2fd; padding: 15px; border-radius: 6px;">
                            <p style="margin: 0 0 10px 0; font-weight: 600; color: #1565c0;">📋 엑셀 형식 (A, B 순서):</p>
                            <p style="margin: 5px 0; color: #1565c0;">A열: 업체명 | B열: 리뷰URL</p>
                        </div>
                    </form>
                    
                    <div style="margin-top: 15px; text-align: center;">
                        <a href="/download-template/reviews" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; font-size: 12px;">📄 리뷰 템플릿 다운로드</a>
                    </div>
                </div>
            </div>
            
            <!-- 영수증 생성기 탭 -->
            <div id="receiptTab" style="display: none;">
                <h3 style="margin-bottom: 20px; color: #333;">🧾 영수증 생성기</h3>
                
                <!-- Step 1: 업체 정보 -->
                <div style="background: white; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="background: #007bff; color: white; padding: 15px; border-radius: 10px 10px 0 0;">
                        <h5 style="margin: 0;"><span style="background: #fff; color: #007bff; width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-weight: bold;">1</span>업체 정보</h5>
                    </div>
                    <div style="padding: 20px;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">상호명 *</label>
                                <input type="text" id="storeName" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px;">
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">사업자번호 *</label>
                                <input type="text" id="bizNum" pattern="[0-9]{3}-[0-9]{2}-[0-9]{5}" placeholder="123-45-67890" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px;">
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">대표자명 *</label>
                                <input type="text" id="ownerName" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px;">
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">전화번호 *</label>
                                <input type="text" id="phone" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px;">
                            </div>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 8px; font-weight: 600;">주소 *</label>
                            <textarea id="address" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; height: 80px;"></textarea>
                        </div>
                    </div>
                </div>

                <!-- Step 2: 메뉴 설정 -->
                <div style="background: white; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="background: #28a745; color: white; padding: 15px; border-radius: 10px 10px 0 0;">
                        <h5 style="margin: 0;"><span style="background: #fff; color: #28a745; width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-weight: bold;">2</span>메뉴 설정</h5>
                    </div>
                    <div style="padding: 20px;">
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 8px; font-weight: 600;">네이버 플레이스 URL (자동 추출)</label>
                            <div style="display: flex; gap: 10px;">
                                <input type="url" id="placeUrl" placeholder="https://place.naver.com/restaurant/1234567890" style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                                <button type="button" onclick="fetchMenuData()" style="padding: 10px 20px; background: #17a2b8; color: white; border: none; border-radius: 5px; font-weight: 600;">메뉴 가져오기</button>
                            </div>
                        </div>
                        
                        <div>
                            <label style="display: block; margin-bottom: 8px; font-weight: 600;">메뉴 목록 * <span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">수동 입력/수정 가능</span></label>
                            <textarea id="menuText" required style="width: 100%; height: 120px; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-family: monospace;" placeholder="김치찌개 8000원&#10;된장찌개 7000원&#10;불고기정식 15000원">김치찌개 8000원
된장찌개 7000원
불고기정식 15000원
비빔밥 9000원
냉면 8000원</textarea>
                            <div style="margin-top: 8px; color: #6c757d;">
                                <i class="fas fa-info-circle"></i> <span id="menuCount">0</span>개 메뉴
                            </div>
                            <div style="margin-top: 10px;">
                                <input type="checkbox" id="applyMenuFilter" checked>
                                <label for="applyMenuFilter" style="margin-left: 8px;">7글자 필터 적용 (공백 제거 후 7글자 이하만 사용)</label>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Step 3: 날짜 및 시간 설정 -->
                <div style="background: white; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="background: #fd7e14; color: white; padding: 15px; border-radius: 10px 10px 0 0;">
                        <h5 style="margin: 0;"><span style="background: #fff; color: #fd7e14; width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-weight: bold;">3</span>날짜 및 시간 설정</h5>
                    </div>
                    <div style="padding: 20px;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">시작 날짜 *</label>
                                <input type="date" id="startDate" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">종료 날짜 *</label>
                                <input type="date" id="endDate" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">일일 개수 *</label>
                                <input type="number" id="dailyCount" min="1" max="100" value="5" required style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">시작 시간</label>
                                <select id="startHour" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                                    <option value="9">09시</option>
                                    <option value="10">10시</option>
                                    <option value="11" selected>11시</option>
                                    <option value="12">12시</option>
                                    <option value="13">13시</option>
                                    <option value="14">14시</option>
                                    <option value="15">15시</option>
                                    <option value="16">16시</option>
                                    <option value="17">17시</option>
                                    <option value="18">18시</option>
                                    <option value="19">19시</option>
                                    <option value="20">20시</option>
                                </select>
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 8px; font-weight: 600;">종료 시간</label>
                                <select id="endHour" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                                    <option value="12">12시</option>
                                    <option value="13">13시</option>
                                    <option value="14">14시</option>
                                    <option value="15">15시</option>
                                    <option value="16">16시</option>
                                    <option value="17">17시</option>
                                    <option value="18">18시</option>
                                    <option value="19">19시</option>
                                    <option value="20">20시</option>
                                    <option value="21" selected>21시</option>
                                    <option value="22">22시</option>
                                    <option value="23">23시</option>
                                </select>
                            </div>
                        </div>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
                            <strong>생성 예정:</strong> <span id="previewText">날짜를 선택하면 총 생성 개수가 표시됩니다.</span>
                        </div>
                    </div>
                </div>
                
                <!-- Step 4: 추가 파일 업로드 -->
                <div style="background: white; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="background: #6f42c1; color: white; padding: 15px; border-radius: 10px 10px 0 0;">
                        <h5 style="margin: 0;"><span style="background: #fff; color: #6f42c1; width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-right: 10px; font-weight: bold;">4</span>추가 파일 업로드 (선택)</h5>
                    </div>
                    <div style="padding: 20px;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                            <div>
                                <h6><i class="fas fa-file-excel" style="color: #28a745;"></i> 엑셀 데이터</h6>
                                <div style="border: 2px dashed #dee2e6; border-radius: 8px; padding: 20px; text-align: center; background: #f8f9fa; cursor: pointer;" id="excelDropArea">
                                    <i class="fas fa-file-upload" style="font-size: 2rem; margin-bottom: 15px; color: #6c757d;"></i>
                                    <p>엑셀 파일을 드래그하거나 클릭하여 선택</p>
                                    <small style="color: #6c757d;">지원: .xlsx, .xls, .csv</small>
                                    <input type="file" id="excelInput" accept=".xlsx,.xls,.csv" style="display: none;">
                                </div>
                                <div id="excelList"></div>
                            </div>
                            <div>
                                <h6><i class="fas fa-images" style="color: #007bff;"></i> 사진 (메타데이터 자동 제거)</h6>
                                <div style="border: 2px dashed #dee2e6; border-radius: 8px; padding: 20px; text-align: center; background: #f8f9fa; cursor: pointer;" id="photoDropArea">
                                    <i class="fas fa-images" style="font-size: 2rem; margin-bottom: 15px; color: #6c757d;"></i>
                                    <p>사진들을 드래그하거나 클릭하여 선택</p>
                                    <small style="color: #6c757d;">순서대로 번호 부여 (1번부터)</small>
                                    <input type="file" id="photoInput" multiple accept="image/*" style="display: none;">
                                </div>
                                <div id="photoList"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 영수증 생성 버튼 -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <button type="button" onclick="generateReceipts()" style="padding: 20px 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; font-size: 18px; font-weight: 600; cursor: pointer; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);">
                        <i class="fas fa-magic"></i> 영수증 생성하기
                    </button>
                </div>
                
                <div id="receiptResult" style="display: none; margin-top: 25px; padding: 20px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px;">
                    <h4 style="color: #155724; margin-bottom: 10px;">✅ 영수증 생성 완료!</h4>
                    <p id="receiptResultText" style="color: #155724; margin: 0;"></p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 초기 날짜 설정
        document.addEventListener('DOMContentLoaded', function() {{
            const today = new Date();
            const lastMonth = new Date(today);
            lastMonth.setMonth(today.getMonth() - 1);
            
            document.getElementById('startDate').value = lastMonth.toISOString().split('T')[0];
            document.getElementById('endDate').value = today.toISOString().split('T')[0];
            
            updatePreview();
        }});

        // 사업자번호 자동 포맷팅
        document.getElementById('bizNum').addEventListener('input', function(e) {{
            let value = e.target.value.replace(/[^0-9]/g, '');
            if (value.length >= 3) {{
                value = value.substring(0,3) + '-' + value.substring(3);
            }}
            if (value.length >= 6) {{
                value = value.substring(0,6) + '-' + value.substring(6);
            }}
            if (value.length > 12) {{
                value = value.substring(0,12);
            }}
            e.target.value = value;
        }});

        // 미리보기 업데이트
        function updatePreview() {{
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const dailyCount = parseInt(document.getElementById('dailyCount').value) || 0;
            
            if (startDate && endDate && dailyCount > 0) {{
                const start = new Date(startDate);
                const end = new Date(endDate);
                const timeDiff = end.getTime() - start.getTime();
                const dayDiff = Math.ceil(timeDiff / (1000 * 3600 * 24)) + 1;
                const totalCount = dayDiff * dailyCount;
                
                document.getElementById('previewText').textContent = `${{dayDiff}}일 × ${{dailyCount}}개 = 총 ${{totalCount}}개 영수증`;
            }} else {{
                document.getElementById('previewText').textContent = '날짜를 선택하면 총 생성 개수가 표시됩니다.';
            }}
        }}

        // 날짜 및 개수 변경시 미리보기 업데이트
        ['startDate', 'endDate', 'dailyCount'].forEach(id => {{
            document.getElementById(id).addEventListener('change', updatePreview);
        }});

        async function fetchMenuData() {{
            const placeUrl = document.getElementById('placeUrl').value;
            if (!placeUrl) {{
                alert('네이버 플레이스 URL을 입력해주세요.');
                return;
            }}

            try {{
                const response = await fetch(`/api/get_naver_menu?url=${{encodeURIComponent(placeUrl)}}`);
                const data = await response.json();
                
                if (data.success) {{
                    document.getElementById('menuText').value = data.menu_text;
                    updateMenuCount();
                    alert(`메뉴 ${{data.total_count}}개를 성공적으로 추출했습니다!`);
                }} else {{
                    alert(`오류: ${{data.error}}`);
                }}
            }} catch (error) {{
                alert(`네트워크 오류: ${{error.message}}`);
            }}
        }}

        function updateMenuCount() {{
            const menuText = document.getElementById('menuText').value.trim();
            const lines = menuText.split('\\n').filter(line => line.trim());
            document.getElementById('menuCount').textContent = lines.length;
        }}

        document.getElementById('menuText').addEventListener('input', updateMenuCount);
        
        // 파일 업로드 기능
        setupFileUpload();
        
        function setupFileUpload() {{
            // 엑셀 파일 업로드
            const excelDropArea = document.getElementById('excelDropArea');
            const excelInput = document.getElementById('excelInput');
            
            excelDropArea.addEventListener('click', () => excelInput.click());
            
            excelDropArea.addEventListener('dragover', (e) => {{
                e.preventDefault();
                excelDropArea.style.borderColor = '#007bff';
                excelDropArea.style.backgroundColor = '#e7f1ff';
            }});
            
            excelDropArea.addEventListener('dragleave', (e) => {{
                e.preventDefault();
                excelDropArea.style.borderColor = '#dee2e6';
                excelDropArea.style.backgroundColor = '#f8f9fa';
            }});
            
            excelDropArea.addEventListener('drop', (e) => {{
                e.preventDefault();
                excelDropArea.style.borderColor = '#dee2e6';
                excelDropArea.style.backgroundColor = '#f8f9fa';
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {{
                    excelInput.files = files;
                    displayExcelFiles(files);
                }}
            }});
            
            excelInput.addEventListener('change', (e) => {{
                displayExcelFiles(e.target.files);
            }});
            
            // 사진 파일 업로드
            const photoDropArea = document.getElementById('photoDropArea');
            const photoInput = document.getElementById('photoInput');
            
            photoDropArea.addEventListener('click', () => photoInput.click());
            
            photoDropArea.addEventListener('dragover', (e) => {{
                e.preventDefault();
                photoDropArea.style.borderColor = '#007bff';
                photoDropArea.style.backgroundColor = '#e7f1ff';
            }});
            
            photoDropArea.addEventListener('dragleave', (e) => {{
                e.preventDefault();
                photoDropArea.style.borderColor = '#dee2e6';
                photoDropArea.style.backgroundColor = '#f8f9fa';
            }});
            
            photoDropArea.addEventListener('drop', (e) => {{
                e.preventDefault();
                photoDropArea.style.borderColor = '#dee2e6';
                photoDropArea.style.backgroundColor = '#f8f9fa';
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {{
                    photoInput.files = files;
                    displayPhotoFiles(files);
                }}
            }});
            
            photoInput.addEventListener('change', (e) => {{
                displayPhotoFiles(e.target.files);
            }});
        }}
        
        function displayExcelFiles(files) {{
            const excelList = document.getElementById('excelList');
            excelList.innerHTML = '';
            
            if (files.length > 0) {{
                const file = files[0];
                const fileItem = document.createElement('div');
                fileItem.style.cssText = 'margin-top: 10px; padding: 10px; background: #e8f5e8; border-radius: 5px;';
                fileItem.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <i class="fas fa-file-excel" style="color: #28a745; margin-right: 8px;"></i>
                            <strong>${{file.name}}</strong>
                            <small style="color: #6c757d;">(${{Math.round(file.size / 1024)}}KB)</small>
                        </div>
                        <button onclick="clearExcelFile()" style="background: #dc3545; color: white; border: none; border-radius: 3px; padding: 5px 10px; cursor: pointer;">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                `;
                excelList.appendChild(fileItem);
            }}
        }}
        
        function displayPhotoFiles(files) {{
            const photoList = document.getElementById('photoList');
            photoList.innerHTML = '';
            
            if (files.length > 0) {{
                const container = document.createElement('div');
                container.style.cssText = 'margin-top: 10px;';
                
                for (let i = 0; i < files.length; i++) {{
                    const file = files[i];
                    const fileItem = document.createElement('div');
                    fileItem.style.cssText = 'margin-bottom: 8px; padding: 8px; background: #e7f1ff; border-radius: 5px; display: flex; justify-content: space-between; align-items: center;';
                    fileItem.innerHTML = `
                        <div>
                            <span style="background: #007bff; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-right: 8px;">${{i + 1}}</span>
                            <i class="fas fa-image" style="color: #007bff; margin-right: 5px;"></i>
                            <strong>${{file.name}}</strong>
                            <small style="color: #6c757d;">(${{Math.round(file.size / 1024)}}KB)</small>
                        </div>
                    `;
                    container.appendChild(fileItem);
                }}
                
                const clearBtn = document.createElement('button');
                clearBtn.onclick = clearPhotoFiles;
                clearBtn.style.cssText = 'margin-top: 5px; background: #dc3545; color: white; border: none; border-radius: 3px; padding: 5px 10px; cursor: pointer;';
                clearBtn.innerHTML = '<i class="fas fa-times"></i> 모든 사진 삭제';
                container.appendChild(clearBtn);
                
                photoList.appendChild(container);
            }}
        }}
        
        function clearExcelFile() {{
            document.getElementById('excelInput').value = '';
            document.getElementById('excelList').innerHTML = '';
        }}
        
        function clearPhotoFiles() {{
            document.getElementById('photoInput').value = '';
            document.getElementById('photoList').innerHTML = '';
        }}

        async function generateReceipts() {{
            // FormData 객체 생성 (파일 업로드 지원)
            const formData = new FormData();
            
            // 기본 정보 추가
            formData.append('store_name', document.getElementById('storeName').value);
            formData.append('biz_num', document.getElementById('bizNum').value);
            formData.append('owner_name', document.getElementById('ownerName').value);
            formData.append('phone', document.getElementById('phone').value);
            formData.append('address', document.getElementById('address').value);
            formData.append('menu_list', document.getElementById('menuText').value);
            formData.append('start_date', document.getElementById('startDate').value);
            formData.append('end_date', document.getElementById('endDate').value);
            formData.append('daily_count', document.getElementById('dailyCount').value);
            formData.append('start_hour', document.getElementById('startHour').value);
            formData.append('end_hour', document.getElementById('endHour').value);
            formData.append('apply_menu_filter', document.getElementById('applyMenuFilter').checked);
            
            // 엑셀 파일 처리
            const excelInput = document.getElementById('excelInput');
            const useExcel = excelInput.files.length > 0;
            formData.append('use_excel', useExcel);
            if (useExcel) {{
                formData.append('excel_file', excelInput.files[0]);
            }}
            
            // 사진 파일들 처리
            const photoInput = document.getElementById('photoInput');
            if (photoInput.files.length > 0) {{
                for (let i = 0; i < photoInput.files.length; i++) {{
                    formData.append('photos', photoInput.files[i]);
                }}
            }}
            
            // 텍스트 내용 (빈 값으로 설정, 향후 확장 가능)
            formData.append('text_content', '');

            // 필수 필드 검증
            const storeName = formData.get('store_name');
            const bizNum = formData.get('biz_num');
            const ownerName = formData.get('owner_name');
            const phone = formData.get('phone');
            const address = formData.get('address');
            const menuList = formData.get('menu_list');
            const startDate = formData.get('start_date');
            const endDate = formData.get('end_date');
            
            if (!storeName || !bizNum || !ownerName || !phone || !address || !menuList || !startDate || !endDate) {{
                alert('모든 필수 항목을 입력해주세요.');
                return;
            }}

            try {{
                // 로딩 상태 표시
                const generateBtn = document.querySelector('button[onclick="generateReceipts()"]');
                const originalText = generateBtn.innerHTML;
                generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 생성 중...';
                generateBtn.disabled = true;
                
                // JSON 형태로 데이터 준비 (기존 API 방식 사용)
                const jsonData = {{
                    store_name: formData.get('store_name'),
                    biz_num: formData.get('biz_num'),
                    owner_name: formData.get('owner_name'),
                    phone: formData.get('phone'),
                    address: formData.get('address'),
                    menu_text: formData.get('menu_list'),
                    start_date: formData.get('start_date'),
                    end_date: formData.get('end_date'),
                    daily_count: parseInt(formData.get('daily_count')),
                    start_hour: parseInt(formData.get('start_hour')),
                    end_hour: parseInt(formData.get('end_hour')),
                    apply_filter: formData.get('apply_menu_filter') === 'true'
                }};

                const response = await fetch('/admin/api/generate-receipts-full', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(jsonData)
                }});

                if (response.ok) {{
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${{storeName}}_고급영수증_${{new Date().getTime()}}.zip`;
                    a.click();
                    window.URL.revokeObjectURL(url);

                    const start = new Date(startDate);
                    const end = new Date(endDate);
                    const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1;
                    const total = days * parseInt(formData.get('daily_count'));
                    
                    let resultText = `<strong>${{total}}개</strong>의 영수증이 생성되어 다운로드되었습니다.`;
                    
                    // 추가 기능 안내
                    if (useExcel) {{
                        resultText += '<br>📊 엑셀 데이터와 통합됨';
                    }}
                    if (photoInput.files.length > 0) {{
                        resultText += `<br>📷 ${{photoInput.files.length}}개 사진 포함됨`;
                    }}
                    
                    document.getElementById('receiptResultText').innerHTML = resultText;
                    document.getElementById('receiptResult').style.display = 'block';
                }} else {{
                    const error = await response.json();
                    alert(`오류: ${{error.detail}}`);
                }}
                
                // 버튼 복구
                generateBtn.innerHTML = originalText;
                generateBtn.disabled = false;
                
            }} catch (error) {{
                alert(`오류: ${{error.message}}`);
                // 버튼 복구
                const generateBtn = document.querySelector('button[onclick="generateReceipts()"]');
                generateBtn.innerHTML = '<i class="fas fa-magic"></i> 영수증 생성하기';
                generateBtn.disabled = false;
            }}
        }}
    </script>
</body>
</html>""")

@app.get("/company/{company_name}")
def company_page(company_name: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 해당 고객사의 업체들
    cursor.execute('SELECT * FROM stores WHERE company_name = ? ORDER BY created_at DESC', (company_name,))
    stores = cursor.fetchall()
    
    # 해당 고객사의 모든 리뷰들 (추출 전도 포함)
    cursor.execute('''
        SELECT r.* FROM reviews r
        JOIN stores s ON r.store_name = s.name
        WHERE s.company_name = ?
        ORDER BY r.created_at DESC
    ''', (company_name,))
    all_reviews = cursor.fetchall()
    
    # 완료된 리뷰만 (CSV 다운로드용)
    completed_reviews = [r for r in all_reviews if r[5] == 'completed']
    
    conn.close()
    
    # 통계 계산
    total_reviews = len(all_reviews)
    completed_count = len([r for r in all_reviews if r[5] == 'completed'])
    pending_count = len([r for r in all_reviews if r[5] == 'pending'])
    failed_count = len([r for r in all_reviews if r[5] == 'failed'])
    
    # 업체별 현황
    stores_html = ''
    search_options = ''
    for s in stores:
        # 종료일 계산
        end_date = ''
        if s[3]:  # start_date
            try:
                start = datetime.strptime(s[3], '%Y-%m-%d')
                end = start + timedelta(days=(s[5] or 30))
                end_date = end.strftime('%Y-%m-%d')
            except:
                end_date = ''
        
        total_target = (s[4] or 1) * (s[5] or 30)
        store_completed = len([r for r in all_reviews if r[1] == s[2] and r[5] == 'completed'])
        store_registered = len([r for r in all_reviews if r[1] == s[2]])  # 등록된 모든 리뷰 (추출 성공/실패 무관)
        percentage = round((store_registered / total_target) * 100) if total_target > 0 else 0
        
        # 상태 판정 (등록 갯수 기준)
        if store_registered >= total_target:
            status = '목표달성'
            status_color = '#28a745'
            card_class = 'completed-store'
        elif store_registered > 0:
            status = '진행중'
            status_color = '#ffc107'
            card_class = 'progress-store'
        else:
            status = '대기'
            status_color = '#6c757d'
            card_class = 'waiting-store'
        
        stores_html += f'''
        <div class="store-card {card_class}" data-store="{s[2]}" style="background: #f8f9fa; border-left: 4px solid {status_color}; padding: 20px; border-radius: 10px; margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div>
                    <h4 style="margin: 0; color: #333; font-size: 18px;">{s[2]}</h4>
                    <span style="padding: 3px 10px; background: {status_color}; color: white; border-radius: 12px; font-size: 11px; font-weight: 600;">{status}</span>
                </div>
                <div>
                    <button onclick="toggleStoreReviews('{s[2]}')" style="padding: 6px 12px; background: #28a745; color: white; border: none; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 8px; cursor: pointer;">👁️ 리뷰보기</button>
                    <a href="/download-store-csv/{company_name}/{s[2]}" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 600;">📊 업체별 리포트</a>
                </div>
            </div>
            <div style="margin-bottom: 10px; color: #666; font-size: 14px;">
                📅 <strong>기간:</strong> {s[3] or '-'} ~ {end_date or '-'} ({s[5] or 30}일)
            </div>
            <div style="margin-bottom: 10px; color: #666; font-size: 14px;">
                🎯 <strong>목표:</strong> {total_target}개 ({s[4] or 1}개/일 × {s[5] or 30}일)
            </div>
            <div style="margin-bottom: 8px; font-size: 16px; font-weight: bold; color: {status_color};">
                📊 등록: {store_registered}/{total_target} ({percentage}%)
            </div>
            <div style="font-size: 14px; color: #666;">
                ✅ 추출완료: {store_completed}개
            </div>
            
            <!-- 업체별 리뷰 목록 (숨김 상태) -->
            <div id="reviews_{s[2].replace(' ', '_')}" style="display: none; margin-top: 15px; background: white; padding: 15px; border-radius: 8px; border: 1px solid #ddd;">
                <h5 style="margin-bottom: 10px; color: #333;">{s[2]} 리뷰 목록</h5>
                <div class="store-reviews-container" data-store="{s[2]}">로딩중...</div>
            </div>
        </div>'''
        
        search_options += f'<option value="{s[2]}">{s[2]}</option>'
    
    if not stores_html:
        stores_html = '<p style="color: #999; text-align: center; padding: 40px;">등록된 업체가 없습니다</p>'
    
    # 모든 리뷰 테이블 (등록 즉시 표시)
    reviews_table = ''
    if all_reviews:
        reviews_table = '''
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <thead style="background: #f8f9fa;">
                <tr>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">업체명</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">리뷰URL</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">리뷰내용</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">영수증날짜</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">상태</th>
                </tr>
            </thead>
            <tbody id="reviewsTable">'''
        
        for r in all_reviews:
            status_color = '#28a745' if r[5] == 'completed' else '#ffc107' if r[5] == 'pending' else '#dc3545'
            status_text = '완료' if r[5] == 'completed' else '대기중' if r[5] == 'pending' else '실패'
            
            reviews_table += f'''
                <tr class="review-row" data-store="{r[1]}">
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: 600;">{r[1]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-size: 11px;"><a href="{r[2]}" target="_blank" style="color: #007bff;">{r[2][:35]}...</a></td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px; line-height: 1.4;">{r[3] or (r[5] == 'pending' and '추출 대기중' or '-')}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: 600; color: #dc3545;">{r[4] or '-'}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: center;"><span style="padding: 4px 8px; background: {status_color}; color: white; border-radius: 12px; font-size: 10px; font-weight: 600;">{status_text}</span></td>
                </tr>'''
        
        reviews_table += '</tbody></table>'
    else:
        reviews_table = '<p style="text-align: center; padding: 40px; color: #999;">등록된 리뷰가 없습니다</p>'
    
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{company_name} 리뷰 현황</title>
    <script>
        function filterByStore() {{
            const selectedStore = document.getElementById('storeFilter').value;
            const storeCards = document.querySelectorAll('.store-card');
            const reviewRows = document.querySelectorAll('.review-row');
            
            storeCards.forEach(card => {{
                if (!selectedStore || card.dataset.store === selectedStore) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
            
            reviewRows.forEach(row => {{
                if (!selectedStore || row.dataset.store === selectedStore) {{
                    row.style.display = 'table-row';
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}
        
        function searchStore() {{
            const searchTerm = document.getElementById('storeSearch').value.toLowerCase();
            const storeCards = document.querySelectorAll('.store-card');
            const reviewRows = document.querySelectorAll('.review-row');
            
            storeCards.forEach(card => {{
                const storeName = card.dataset.store.toLowerCase();
                if (!searchTerm || storeName.includes(searchTerm)) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
            
            reviewRows.forEach(row => {{
                const storeName = row.dataset.store.toLowerCase();
                if (!searchTerm || storeName.includes(searchTerm)) {{
                    row.style.display = 'table-row';
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}
    </script>
</head>
<body style="font-family: Arial; background: #f5f7fa; margin: 0; padding: 20px;">
    <div style="max-width: 1200px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #28a745, #20c997); color: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; text-align: center;">
            <h1 style="margin: 0 0 10px 0; font-size: 2.2rem;">🏢 {company_name}</h1>
            <p style="margin: 0; opacity: 0.9;">리뷰 현황 관리 및 리포트 다운로드</p>
            <a href="/" style="margin-top: 15px; display: inline-block; color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px;">로그아웃</a>
        </div>
        
        <!-- 전체 현황 요약 -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 25px;">
            <div style="background: white; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #007bff;">
                <h3 style="margin: 0 0 10px 0; color: #007bff;">전체 리뷰</h3>
                <p style="margin: 0; font-size: 2rem; font-weight: bold; color: #333;">{total_reviews}</p>
            </div>
            <div style="background: white; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #28a745;">
                <h3 style="margin: 0 0 10px 0; color: #28a745;">완료</h3>
                <p style="margin: 0; font-size: 2rem; font-weight: bold; color: #333;">{completed_count}</p>
            </div>
            <div style="background: white; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #ffc107;">
                <h3 style="margin: 0 0 10px 0; color: #ffc107;">대기중</h3>
                <p style="margin: 0; font-size: 2rem; font-weight: bold; color: #333;">{pending_count}</p>
            </div>
            <div style="background: white; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #dc3545;">
                <h3 style="margin: 0 0 10px 0; color: #dc3545;">실패</h3>
                <p style="margin: 0; font-size: 2rem; font-weight: bold; color: #333;">{failed_count}</p>
            </div>
        </div>
        
        <div style="background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px;">
            <!-- 검색 및 필터 -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                <h3 style="margin: 0; color: #333;">🏪 업체별 현황</h3>
                <div style="display: flex; gap: 15px;">
                    <a href="/download-csv/{company_name}" style="padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">📊 전체 CSV 다운로드</a>
                </div>
            </div>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 15px; align-items: center;">
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">업체 필터</label>
                        <select id="storeFilter" onchange="filterByStore()" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                            <option value="">전체 업체</option>
                            {search_options}
                        </select>
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #555;">업체명 검색</label>
                        <input id="storeSearch" type="text" placeholder="업체명 입력" onkeyup="searchStore()" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                    <button onclick="document.getElementById('storeFilter').value=''; document.getElementById('storeSearch').value=''; filterByStore(); searchStore();" style="padding: 8px 16px; background: #6c757d; color: white; border: none; border-radius: 4px;">초기화</button>
                </div>
            </div>
            
            <!-- 업체별 현황 카드 -->
            <div style="margin-bottom: 30px;">
                <!-- 진행중 업체들 -->
                <div id="progressStores">
                    <h4 style="margin-bottom: 15px; color: #495057;">🚀 진행중/대기 업체</h4>
                    <div class="progress-stores-container"></div>
                </div>
                
                <!-- 완료된 업체들 -->
                <div id="completedStores" style="margin-top: 30px;">
                    <h4 style="margin-bottom: 15px; color: #495057;">✅ 완료된 업체</h4>
                    <div class="completed-stores-container"></div>
                </div>
                
                <!-- 전체 업체 (기본 표시) -->
                <div id="allStores">
                    {stores_html}
                </div>
            </div>
            
            <!-- 업체 상태별 필터 버튼 -->
            <div style="text-align: center; margin-bottom: 20px;">
                <button onclick="showStoresByStatus('all')" id="allBtn" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 6px; margin: 0 5px; cursor: pointer;">전체</button>
                <button onclick="showStoresByStatus('progress')" id="progressBtn" style="padding: 8px 16px; background: #f8f9fa; color: #333; border: 1px solid #ddd; border-radius: 6px; margin: 0 5px; cursor: pointer;">진행중/대기</button>
                <button onclick="showStoresByStatus('completed')" id="completedBtn" style="padding: 8px 16px; background: #f8f9fa; color: #333; border: 1px solid #ddd; border-radius: 6px; margin: 0 5px; cursor: pointer;">완료</button>
            </div>
            
            <script>
                function showStoresByStatus(status) {{
                    const allStores = document.getElementById('allStores');
                    const progressStores = document.getElementById('progressStores');
                    const completedStores = document.getElementById('completedStores');
                    
                    // 버튼 스타일 업데이트
                    ['allBtn', 'progressBtn', 'completedBtn'].forEach(btnId => {{
                        const btn = document.getElementById(btnId);
                        btn.style.background = '#f8f9fa';
                        btn.style.color = '#333';
                        btn.style.border = '1px solid #ddd';
                    }});
                    
                    document.getElementById(status + 'Btn').style.background = '#007bff';
                    document.getElementById(status + 'Btn').style.color = 'white';
                    document.getElementById(status + 'Btn').style.border = 'none';
                    
                    // 업체 표시/숨김
                    if (status === 'all') {{
                        allStores.style.display = 'block';
                        progressStores.style.display = 'none';
                        completedStores.style.display = 'none';
                    }} else {{
                        allStores.style.display = 'none';
                        
                        if (status === 'progress') {{
                            progressStores.style.display = 'block';
                            completedStores.style.display = 'none';
                            
                            // 진행중/대기 업체들만 표시
                            const progressContainer = document.querySelector('.progress-stores-container');
                            progressContainer.innerHTML = '';
                            document.querySelectorAll('.progress-store, .waiting-store').forEach(card => {{
                                progressContainer.appendChild(card.cloneNode(true));
                            }});
                        }} else {{
                            progressStores.style.display = 'none';
                            completedStores.style.display = 'block';
                            
                            // 완료된 업체들만 표시
                            const completedContainer = document.querySelector('.completed-stores-container');
                            completedContainer.innerHTML = '';
                            document.querySelectorAll('.completed-store').forEach(card => {{
                                completedContainer.appendChild(card.cloneNode(true));
                            }});
                        }}
                    }}
                }}
            
            // 업체별 리뷰 펼쳐보기/접기
            async function toggleStoreReviews(storeName) {{
                const reviewsDiv = document.getElementById('reviews_' + storeName.replace(/\s+/g, '_'));
                const container = document.querySelector(`[data-store="${{storeName}}"]`);
                const button = event.target;
                
                if (reviewsDiv.style.display === 'none') {{
                    // 펼치기 - 서버에서 해당 업체 리뷰 데이터 가져오기
                    reviewsDiv.style.display = 'block';
                    button.innerText = '🔼 접기';
                    container.innerHTML = '<div style="text-align: center; padding: 20px;"><div style="display: inline-block; width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #007bff; border-radius: 50%; animation: spin 1s linear infinite;"></div><p>로딩중...</p></div>';
                    
                    try {{
                        const response = await fetch(`/api/store-reviews/${{encodeURIComponent(storeName)}}`);
                        const data = await response.json();
                        
                        let reviewsHtml = '<div style="max-height: 400px; overflow-y: auto;">';
                        
                        if (data.length > 0) {{
                            // 영수증 날짜 기준 정렬 (최신순)
                            data.sort((a, b) => {{
                                const dateA = a.extracted_date || '0000.00.00';
                                const dateB = b.extracted_date || '0000.00.00';
                                return dateB.localeCompare(dateA);
                            }});
                            
                            data.forEach((review, index) => {{
                                const statusColor = review.status === 'completed' ? '#28a745' : review.status === 'pending' ? '#ffc107' : '#dc3545';
                                const statusText = review.status === 'completed' ? '완료' : review.status === 'pending' ? '대기' : '실패';
                                
                                reviewsHtml += `
                                <div style="background: ${{review.status === 'completed' ? '#f8f9fa' : '#fff3cd'}}; margin-bottom: 12px; padding: 15px; border-radius: 8px; border-left: 4px solid ${{statusColor}};">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                        <div>
                                            <span style="font-weight: 600; color: #333;">리뷰 ${{index + 1}}</span>
                                            <span style="margin-left: 10px; padding: 2px 8px; background: ${{statusColor}}; color: white; border-radius: 10px; font-size: 10px; font-weight: 600;">${{statusText}}</span>
                                            <span style="margin-left: 10px; color: #dc3545; font-weight: 600; font-size: 13px;">📅 ${{review.extracted_date || '-'}}</span>
                                        </div>
                                        <a href="${{review.review_url}}" target="_blank" style="padding: 4px 8px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; font-size: 10px;">🔗 원본</a>
                                    </div>
                                    <div style="color: #666; font-size: 11px; margin-bottom: 8px;">
                                        <strong>URL:</strong> ${{review.review_url.substring(0, 50)}}...
                                    </div>
                                    ${{review.extracted_text ? `
                                    <div style="background: white; padding: 12px; border-radius: 6px; font-size: 13px; line-height: 1.5; color: #333;">
                                        ${{review.extracted_text}}
                                    </div>` : `
                                    <div style="background: #e9ecef; padding: 10px; border-radius: 6px; text-align: center; color: #666; font-style: italic;">
                                        ${{review.status === 'pending' ? '추출 대기중' : '추출 실패 또는 내용 없음'}}
                                    </div>`}}
                                </div>`;
                            }});
                        }} else {{
                            reviewsHtml += '<div style="text-align: center; padding: 40px; color: #999;"><p style="font-size: 16px;">📭 등록된 리뷰가 없습니다</p><p style="font-size: 12px;">리뷰어가 URL을 등록하면 여기에 표시됩니다</p></div>';
                        }}
                        
                        reviewsHtml += '</div>';
                        container.innerHTML = reviewsHtml;
                    }} catch (error) {{
                        container.innerHTML = '<p style="color: #dc3545; text-align: center; padding: 20px;">데이터 로드 실패</p>';
                    }}
                }} else {{
                    // 접기
                    reviewsDiv.style.display = 'none';
                    button.innerText = '👁️ 리뷰보기';
                }}
            }}
            
            // CSS 애니메이션 추가
            const style = document.createElement('style');
            style.textContent = `
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            `;
            document.head.appendChild(style);
            </script>
            
            <!-- 전체 리뷰 목록 -->
            <div>
                <h4 style="margin-bottom: 15px; color: #495057;">📝 전체 리뷰 목록 (등록 즉시 표시)</h4>
                <div style="background: #e8f5e8; padding: 12px; border-radius: 6px; margin-bottom: 15px; text-align: center;">
                    <p style="margin: 0; color: #155724; font-weight: 600;">✨ 리뷰어가 URL을 등록하면 즉시 여기에 표시됩니다</p>
                    <p style="margin: 5px 0 0 0; color: #155724; font-size: 12px;">관리자가 추출을 완료하면 리뷰 내용이 채워집니다</p>
                </div>
                {reviews_table}
            </div>
        </div>
    </div>
</body>
</html>""")

# API들
@app.post("/create-company")
async def create_company(name: str = Form(), password: str = Form()):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute('INSERT INTO users (username, password_hash, user_type, company_name) VALUES (?, ?, ?, ?)', 
                  (name, password_hash, 'company', name))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.post("/create-store")
async def create_store(company_name: str = Form(), name: str = Form(), start_date: str = Form(""), daily_count: int = Form(1), duration_days: int = Form(30)):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('INSERT INTO stores (company_name, name, start_date, daily_count, duration_days) VALUES (?, ?, ?, ?, ?)',
                  (company_name, name, start_date, daily_count, duration_days))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.post("/create-reviewer")
async def create_reviewer(name: str = Form(), password: str = Form()):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        cursor.execute('INSERT INTO users (username, password_hash, user_type) VALUES (?, ?, ?)', 
                      (name, password_hash, 'reviewer'))
        conn.commit()
        conn.close()
        return RedirectResponse(url="/admin", status_code=302)
    except sqlite3.IntegrityError:
        conn.close()
        return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>생성 실패</title></head>
<body style="font-family: Arial; text-align: center; padding: 50px;">
    <h2 style="color: #dc3545;">리뷰어 생성 실패</h2>
    <p>'{name}' 이미 존재하는 리뷰어명입니다.</p>
    <a href="/admin" style="padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">관리자 페이지로</a>
</body>
</html>""")

@app.post("/create-assignment")
async def create_assignment(reviewer_username: str = Form(), store_id: int = Form()):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('INSERT INTO assignments (reviewer_username, store_id) VALUES (?, ?)', 
                  (reviewer_username, store_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/download-csv/{company_name}")
async def download_csv(company_name: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.store_name, r.review_url, r.extracted_text, r.extracted_date
        FROM reviews r
        JOIN stores s ON r.store_name = s.name
        WHERE s.company_name = ? AND r.status = "completed"
        ORDER BY r.store_name, r.created_at
    ''', (company_name,))
    
    reviews = cursor.fetchall()
    conn.close()
    
    csv_content = "업체명,리뷰URL,리뷰내용,영수증날짜\n"
    for r in reviews:
        content = (r[2] or "").replace('"', '""')
        csv_content += f'"{r[0]}","{r[1]}","{content}","{r[3] or ""}"\n'
    
    # URL 인코딩으로 한글 파일명 지원
    import urllib.parse
    encoded_filename = urllib.parse.quote(f"{company_name}_전체리포트.csv".encode('utf-8'))
    
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type='text/csv',
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

@app.get("/download-store-csv/{company_name}/{store_name}")
async def download_store_csv(company_name: str, store_name: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.store_name, r.review_url, r.extracted_text, r.extracted_date, r.status
        FROM reviews r
        WHERE r.store_name = ?
        ORDER BY r.created_at
    ''', (store_name,))
    
    reviews = cursor.fetchall()
    conn.close()
    
    completed_count = len([r for r in reviews if r[4] == 'completed'])
    
    csv_content = f"{store_name} 리뷰 현황 보고서\n"
    csv_content += f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    csv_content += f"총 등록: {len(reviews)}개\n"
    csv_content += f"추출완료: {completed_count}개\n"
    csv_content += "\n"
    csv_content += "업체명,리뷰URL,리뷰내용,영수증날짜\n"
    
    for r in reviews:
        content = (r[2] or "추출대기중").replace('"', '""')
        date_info = r[3] or (r[4] == 'pending' and '추출대기중' or '-')
        csv_content += f'"{r[0]}","{r[1]}","{content}","{date_info}"\n'
    
    # URL 인코딩으로 한글 파일명 지원
    import urllib.parse
    encoded_filename = urllib.parse.quote(f"{store_name}_리포트.csv".encode('utf-8'))
    
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type='text/csv',
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

@app.get("/reviewer/{reviewer_name}")
def reviewer_page(reviewer_name: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 배정된 업체들
    cursor.execute('''
        SELECT s.* FROM assignments a
        JOIN stores s ON a.store_id = s.id
        WHERE a.reviewer_username = ?
    ''', (reviewer_name,))
    assigned_stores = cursor.fetchall()
    
    # 내 리뷰들
    cursor.execute('SELECT * FROM reviews WHERE registered_by = ? ORDER BY created_at DESC', (reviewer_name,))
    my_reviews = cursor.fetchall()
    
    conn.close()
    
    # 배정된 업체를 완료/진행중으로 분류
    active_stores_html = ''
    completed_stores_html = ''
    
    for s in assigned_stores:
        my_store_reviews = len([r for r in my_reviews if r[1] == s[2]])
        target_count = (s[4] or 1) * (s[5] or 30)  # 목표 갯수
        
        if my_store_reviews >= target_count:
            # 완료된 업체
            completed_stores_html += f'''
            <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #28a745;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin: 0; color: #333; font-size: 16px;">{s[2]}</h4>
                        <span style="padding: 2px 8px; background: #28a745; color: white; border-radius: 10px; font-size: 10px;">목표달성</span>
                    </div>
                    <div style="color: #155724; font-weight: 600;">✅ {my_store_reviews}/{target_count}</div>
                </div>
            </div>'''
        else:
            # 진행중 업체
            percentage = round((my_store_reviews / target_count) * 100) if target_count > 0 else 0
            active_stores_html += f'''
            <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #007bff;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <div>
                        <h4 style="margin: 0; color: #333; font-size: 18px;">{s[2]}</h4>
                        <span style="color: #666; font-size: 12px;">목표: {target_count}개</span>
                    </div>
                    <a href="/add-review-form/{reviewer_name}/{s[2]}" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">+ 리뷰 추가</a>
                </div>
                <div style="color: #666; font-size: 14px;">
                    📊 진행: {my_store_reviews}/{target_count} ({percentage}%)
                </div>
            </div>'''
    
    if not active_stores_html and not completed_stores_html:
        active_stores_html = '<p style="color: #999; text-align: center; padding: 40px;">배정된 업체가 없습니다. 관리자에게 업체 배정을 요청하세요.</p>'
    
    # 내 리뷰 테이블
    reviews_table = ''
    if my_reviews:
        reviews_table = '''
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <thead style="background: #f8f9fa;">
                <tr>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">업체명</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">리뷰URL</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">추출된 내용</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">영수증날짜</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">상태</th>
                </tr>
            </thead>
            <tbody>'''
        
        for r in my_reviews:
            status_color = '#28a745' if r[5] == 'completed' else '#ffc107' if r[5] == 'pending' else '#dc3545'
            status_text = '완료' if r[5] == 'completed' else '대기중' if r[5] == 'pending' else '실패'
            
            reviews_table += f'''
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: 600;">{r[1]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-size: 11px;"><a href="{r[2]}" target="_blank" style="color: #007bff;">{r[2][:30]}...</a></td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">{r[3] or (r[5] == 'pending' and '추출 대기중' or '-')}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: 600;">{r[4] or '-'}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: center;"><span style="padding: 4px 8px; background: {status_color}; color: white; border-radius: 12px; font-size: 10px; font-weight: 600;">{status_text}</span></td>
                </tr>'''
        
        reviews_table += '</tbody></table>'
    else:
        reviews_table = '<p style="text-align: center; padding: 40px; color: #999;">등록한 리뷰가 없습니다</p>'
    
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{reviewer_name} 리뷰어</title>
</head>
<body style="font-family: Arial; background: #f5f7fa; margin: 0; padding: 20px;">
    <div style="max-width: 1000px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #6f42c1, #e83e8c); color: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; text-align: center;">
            <h1 style="margin: 0 0 10px 0; font-size: 2.2rem;">👤 {reviewer_name}</h1>
            <p style="margin: 0; opacity: 0.9;">배정된 업체의 리뷰 URL 등록</p>
            <a href="/" style="margin-top: 15px; display: inline-block; color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px;">로그아웃</a>
        </div>
        
        <!-- 진행중 업체 -->
        <div style="background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px; margin-bottom: 25px;">
            <h3 style="margin-bottom: 20px; color: #333;">🚀 진행중 업체</h3>
            {active_stores_html}
        </div>
        
        <!-- 완료된 업체 -->
        {f'''<div style="background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px; margin-bottom: 25px;">
            <h3 style="margin-bottom: 20px; color: #333;">✅ 완료된 업체</h3>
            {completed_stores_html}
        </div>''' if completed_stores_html else ""}
        
        <div style="background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px;">
            <h3 style="margin-bottom: 20px; color: #333;">📝 내가 등록한 리뷰</h3>
            {reviews_table}
            
            <div style="margin-top: 25px; padding: 20px; background: #fff3cd; border-radius: 10px; text-align: center;">
                <p style="margin: 0; color: #856404; font-weight: 600;">⚠️ 리뷰 내용 추출은 관리자만 수행할 수 있습니다</p>
                <p style="margin: 5px 0 0 0; color: #856404; font-size: 14px;">등록하신 리뷰는 관리자가 추출 완료 후 결과를 확인할 수 있습니다</p>
            </div>
        </div>
    </div>
</body>
</html>""")


@app.get("/add-review-form/{reviewer_name}/{store_name}")
def add_review_form(reviewer_name: str, store_name: str):
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>리뷰 추가</title>
</head>
<body style="font-family: Arial; background: #f5f7fa; margin: 0; padding: 20px;">
    <div style="max-width: 700px; margin: 100px auto;">
        <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); text-align: center;">
            <h2 style="margin-bottom: 20px; color: #333;">📝 {store_name} 리뷰 추가</h2>
            <p style="margin-bottom: 25px; color: #666;">담당 업체에 새로운 리뷰 URL을 등록합니다</p>
            
            <form action="/submit-review" method="post">
                <input type="hidden" name="store_name" value="{store_name}">
                <input type="hidden" name="registered_by" value="{reviewer_name}">
                
                <div style="margin-bottom: 25px;">
                    <input name="review_url" type="url" placeholder="네이버 리뷰 URL을 입력하세요" 
                           style="width: 100%; padding: 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px;" required>
                </div>
                
                <div style="margin-bottom: 25px; padding: 20px; background: #e8f5e8; border-radius: 10px; text-align: left;">
                    <h4 style="margin: 0 0 15px 0; color: #155724;">✨ 지원하는 네이버 리뷰 링크 형식:</h4>
                    <div style="margin-bottom: 10px;">
                        <strong style="color: #155724;">1. 단축 URL:</strong>
                        <code style="background: white; padding: 5px 10px; border-radius: 5px; margin-left: 10px; color: #007bff;">https://naver.me/5jBm0HYx</code>
                    </div>
                    <div>
                        <strong style="color: #155724;">2. 직접 리뷰 링크:</strong>
                        <code style="background: white; padding: 5px 10px; border-radius: 5px; margin-left: 10px; color: #007bff;">https://m.place.naver.com/my/review/...</code>
                    </div>
                </div>
                
                <div style="display: flex; gap: 15px; justify-content: center;">
                    <button type="submit" style="padding: 15px 30px; background: #007bff; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;">📝 리뷰 등록</button>
                    <a href="/reviewer/{reviewer_name}" style="padding: 15px 30px; background: #6c757d; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">❌ 취소</a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>""")

@app.post("/submit-review")
async def submit_review(store_name: str = Form(), review_url: str = Form(), registered_by: str = Form()):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 중복 URL 체크
    cursor.execute('SELECT * FROM reviews WHERE review_url = ?', (review_url,))
    existing_url = cursor.fetchone()
    
    if existing_url:
        conn.close()
        return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>중복 URL 감지</title></head>
<body style="font-family: Arial; background: #f5f7fa; text-align: center; padding: 50px;">
    <div style="background: white; padding: 40px; border-radius: 15px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
        <h2 style="color: #dc3545; margin-bottom: 20px;">⚠️ 중복 URL 감지</h2>
        <p style="margin-bottom: 15px; font-size: 16px;">이미 등록된 리뷰 URL입니다!</p>
        <div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <p style="margin: 5px 0; color: #721c24;"><strong>기존 등록:</strong> {existing_url[1]} ({existing_url[6]})</p>
            <p style="margin: 5px 0; color: #721c24;"><strong>상태:</strong> {existing_url[5]}</p>
        </div>
        <div style="display: flex; gap: 15px; justify-content: center;">
            <a href="/reviewer/{registered_by}" style="padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 6px;">돌아가기</a>
            <a href="/add-review-form/{registered_by}/{store_name}" style="padding: 12px 24px; background: #6c757d; color: white; text-decoration: none; border-radius: 6px;">다른 URL 입력</a>
        </div>
    </div>
</body>
</html>""")
    
    cursor.execute('INSERT INTO reviews (store_name, review_url, registered_by, status) VALUES (?, ?, ?, "pending")',
                  (store_name, review_url, registered_by))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/reviewer/{registered_by}", status_code=302)

@app.get("/process-all")
async def process_all(background_tasks: BackgroundTasks):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM reviews WHERE status = "pending"')
    pending_reviews = cursor.fetchall()
    conn.close()
    
    for review in pending_reviews:
        background_tasks.add_task(extract_review, review[0])
    
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>일괄 처리 시작</title></head>
<body style="font-family: Arial; background: #f5f7fa; text-align: center; padding: 50px;">
    <div style="background: white; padding: 40px; border-radius: 15px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
        <h2 style="color: #28a745; margin-bottom: 20px;">🚀 전체 리뷰 추출 시작!</h2>
        <p style="margin-bottom: 15px; font-size: 18px; font-weight: 600;">{len(pending_reviews)}개의 대기 리뷰 처리 시작</p>
        <p style="margin-bottom: 25px; color: #666;">각 리뷰마다 Chrome이 자동으로 네이버에 접속하여 실제 리뷰 내용과 영수증 날짜를 추출합니다.</p>
        <div style="margin-bottom: 25px; padding: 15px; background: #e8f5e8; border-radius: 8px;">
            <p style="margin: 0; color: #155724; font-weight: 600;">⏰ 예상 소요 시간: 약 {len(pending_reviews) * 15}초</p>
        </div>
        <a href="/admin" style="padding: 15px 30px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">관리자 페이지로 돌아가기</a>
    </div>
</body>
</html>""")

@app.get("/process-review/{review_id}")
async def process_review(review_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(extract_review, review_id)
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>리뷰 추출 시작</title></head>
<body style="font-family: Arial; background: #f5f7fa; text-align: center; padding: 50px;">
    <div style="background: white; padding: 40px; border-radius: 15px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
        <h2 style="color: #007bff; margin-bottom: 20px;">🔍 리뷰 추출 시작!</h2>
        <p style="margin-bottom: 15px; font-size: 16px;">실제 네이버 리뷰 추출이 시작되었습니다.</p>
        <p style="margin-bottom: 25px; color: #666;">Chrome이 자동으로 열려 네이버에 접속하여 리뷰 내용을 찾습니다.</p>
        <div style="margin-bottom: 25px; padding: 15px; background: #fff3cd; border-radius: 8px;">
            <p style="margin: 0; color: #856404; font-weight: 600;">⏰ 약 15-30초 후 결과를 확인하세요</p>
        </div>
        <a href="/admin" style="padding: 15px 30px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">관리자 페이지로 돌아가기</a>
    </div>
</body>
</html>""")

@app.post("/add-review")
async def add_review(store_id: int = Form(), review_url: str = Form()):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 중복 URL 체크
    cursor.execute('SELECT * FROM reviews WHERE review_url = ?', (review_url,))
    existing_url = cursor.fetchone()
    
    if existing_url:
        conn.close()
        return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>중복 URL 감지 (관리자)</title></head>
<body style="font-family: Arial; background: #f5f7fa; text-align: center; padding: 50px;">
    <div style="background: white; padding: 40px; border-radius: 15px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
        <h2 style="color: #dc3545; margin-bottom: 20px;">⚠️ 중복 URL 감지</h2>
        <p style="margin-bottom: 15px; font-size: 16px;">이미 등록된 리뷰 URL입니다!</p>
        <div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <p style="margin: 5px 0; color: #721c24;"><strong>기존 등록 업체:</strong> {existing_url[1]}</p>
            <p style="margin: 5px 0; color: #721c24;"><strong>등록자:</strong> {existing_url[6]}</p>
            <p style="margin: 5px 0; color: #721c24;"><strong>상태:</strong> {existing_url[5]}</p>
        </div>
        <a href="/admin" style="padding: 15px 30px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">관리자 페이지로 돌아가기</a>
    </div>
</body>
</html>""")
    
    # store_id로 업체명 찾기
    cursor.execute('SELECT name FROM stores WHERE id = ?', (store_id,))
    store_result = cursor.fetchone()
    store_name = store_result[0] if store_result else 'Unknown'
    
    cursor.execute('INSERT INTO reviews (store_name, review_url, registered_by, status) VALUES (?, ?, ?, "pending")',
                  (store_name, review_url, 'admin'))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

def extract_review(review_id: int):
    """실제 네이버 리뷰 추출 함수"""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT store_name, review_url FROM reviews WHERE id = ?', (review_id,))
        result = cursor.fetchone()
        if not result:
            return
        
        store_name, review_url = result
        cursor.execute('UPDATE reviews SET status = "processing" WHERE id = ?', (review_id,))
        conn.commit()
        
        print(f"추출 시작: {store_name}")
        
        # 실제 네이버 리뷰 추출
        try:
            from selenium import webdriver
            from selenium.webdriver.support.ui import WebDriverWait
            from bs4 import BeautifulSoup
            import time
            
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User-Agent 변경 (봇 감지 방지)
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 서버 환경 감지
            if os.getenv('DISPLAY') or os.path.exists('/usr/bin/google-chrome'):  # 서버 환경
                options.add_argument('--headless')
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--disable-extensions')
                print("서버 환경에서 headless 모드로 실행")
            else:
                print("로컬 환경에서 일반 모드로 실행")
            
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(10)
            driver.set_page_load_timeout(30)
            
            print(f"Chrome 실행 성공, URL 접속 시작: {review_url}")
            driver.get(review_url)
            print("페이지 로딩 완료")
            
            if "/my/review/" in review_url:
                # 직접 리뷰 링크
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                review_elem = soup.find('a', {'data-pui-click-code': 'reviewend.text'})
                text = review_elem.get_text(strip=True) if review_elem else "리뷰 본문을 찾을 수 없습니다"
                
                # 영수증 날짜 추출 (여러 방법 시도)
                date = "영수증 날짜를 찾을 수 없습니다"
                
                # 방법 1: aria-hidden='true' time 태그
                time_elem = soup.find('time', {'aria-hidden': 'true'})
                if time_elem:
                    date = time_elem.get_text(strip=True)
                    print(f"방법1 - aria-hidden time: {date}")
                
                # 방법 2: 모든 time 태그 확인
                if date == "영수증 날짜를 찾을 수 없습니다":
                    all_time_elems = soup.find_all('time')
                    for time_tag in all_time_elems:
                        time_text = time_tag.get_text(strip=True)
                        if '.' in time_text and any(day in time_text for day in ['월', '화', '수', '목', '금', '토', '일']):
                            date = time_text
                            print(f"방법2 - 모든 time 태그: {date}")
                            break
                
                # 방법 3: 날짜 패턴 텍스트 검색
                if date == "영수증 날짜를 찾을 수 없습니다":
                    import re
                    page_text = soup.get_text()
                    date_pattern = r'\d{1,2}\.\d{1,2}\.[월화수목금토일]'
                    matches = re.findall(date_pattern, page_text)
                    if matches:
                        date = matches[0]  # 첫 번째 매칭 사용
                        print(f"방법3 - 텍스트 패턴: {date}")
                
                print(f"최종 추출된 날짜: {date}")
                
                print(f"직접 링크 추출: {text[:30]}... / {date}")
            else:
                # 단축 URL
                if "naver.me" in review_url:
                    WebDriverWait(driver, 10).until(lambda d: d.current_url != review_url)
                    print(f"리디렉션 완료: {driver.current_url}")
                
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                target_review = None
                
                review_blocks = soup.find_all('div', class_='hahVh2')
                print(f"리뷰 블록 {len(review_blocks)}개 발견")
                
                for block in review_blocks:
                    shop_elem = block.find('span', class_='pui__pv1E2a')
                    if shop_elem:
                        found_name = shop_elem.text.strip()
                        print(f"발견된 업체명: {found_name}")
                        if found_name == store_name:
                            target_review = block
                            print(f"'{store_name}' 매칭 성공!")
                            break
                
                if target_review:
                    # 더보기 버튼 클릭 시도
                    try:
                        from selenium.webdriver.common.by import By
                        more_button_elem = target_review.find('a', {'data-pui-click-code': 'otherreviewfeed.rvshowmore'})
                        if more_button_elem:
                            # Selenium으로 해당 요소 찾아서 클릭
                            review_blocks_selenium = driver.find_elements(By.CSS_SELECTOR, "div.hahVh2")
                            for selenium_block in review_blocks_selenium:
                                if store_name in selenium_block.text:
                                    try:
                                        more_btn = selenium_block.find_element(By.CSS_SELECTOR, "a[data-pui-click-code='otherreviewfeed.rvshowmore']")
                                        if more_btn.is_displayed():
                                            driver.execute_script("arguments[0].click();", more_btn)
                                            time.sleep(1)
                                            print(f"더보기 버튼 클릭 성공: {store_name}")
                                            # 다시 파싱
                                            soup = BeautifulSoup(driver.page_source, 'html.parser')
                                            review_blocks = soup.find_all('div', class_='hahVh2')
                                            for block in review_blocks:
                                                shop_elem = block.find('span', class_='pui__pv1E2a')
                                                if shop_elem and shop_elem.text.strip() == store_name:
                                                    target_review = block
                                                    break
                                        break
                                    except:
                                        pass
                    except Exception as e:
                        print(f"더보기 버튼 클릭 실패: {e}")
                    
                    review_div = target_review.find('div', class_='pui__vn15t2')
                    text = review_div.text.strip() if review_div else "리뷰 본문을 찾을 수 없습니다"
                    
                    # 영수증 날짜 추출 (단축 URL - 여러 방법 시도)
                    date = "영수증 날짜를 찾을 수 없습니다"
                    
                    # 방법 1: 해당 리뷰 블록에서 time 태그
                    time_elem = target_review.find('time', {'aria-hidden': 'true'})
                    if time_elem:
                        date = time_elem.text.strip()
                        print(f"단축URL 방법1: {date}")
                    
                    # 방법 2: 모든 time 태그에서 날짜 형식 찾기
                    if date == "영수증 날짜를 찾을 수 없습니다":
                        all_times = target_review.find_all('time')
                        for time_tag in all_times:
                            time_text = time_tag.get_text(strip=True)
                            if '.' in time_text and any(day in time_text for day in ['월', '화', '수', '목', '금', '토', '일']):
                                date = time_text
                                print(f"단축URL 방법2: {date}")
                                break
                    
                    # 방법 3: 리뷰 블록 전체 텍스트에서 패턴 검색
                    if date == "영수증 날짜를 찾을 수 없습니다":
                        import re
                        block_text = target_review.get_text()
                        date_pattern = r'\d{1,2}\.\d{1,2}\.[월화수목금토일]'
                        matches = re.findall(date_pattern, block_text)
                        if matches:
                            date = matches[-1]  # 마지막 매칭 (보통 영수증 날짜가 뒤에)
                            print(f"단축URL 방법3: {date}")
                    
                    print(f"단축URL 최종 날짜: {date}")
                    
                    print(f"단축 URL 추출: {text[:30]}... / {date}")
                else:
                    text = f"업체명 '{store_name}'과 일치하는 리뷰를 찾을 수 없습니다"
                    date = "날짜 정보 없음"
                    print(f"업체명 매칭 실패: {store_name}")
                    
                    # 발견된 업체명들 출력
                    print("페이지에서 발견된 업체명들:")
                    for i, block in enumerate(review_blocks[:10]):
                        shop_elem = block.find('span', class_='pui__pv1E2a')
                        if shop_elem:
                            print(f"  {i+1}. {shop_elem.text.strip()}")
            
            driver.quit()
            
            # 추출 성공 여부만 판정 (내용 중복 체크 제거)
            if "찾을 수 없습니다" not in text and len(text) > 10:
                status = 'completed'
                cursor.execute('UPDATE reviews SET status = ?, extracted_text = ?, extracted_date = ? WHERE id = ?',
                              (status, text, date, review_id))
                print(f"추출 완료: {store_name} - {status}")
            else:
                status = 'failed'
                cursor.execute('UPDATE reviews SET status = ?, extracted_text = ?, extracted_date = ? WHERE id = ?',
                              (status, text, date, review_id))
                print(f"추출 실패: {store_name} - {status}")
            
        except Exception as e:
            print(f"Chrome 실행 실패: {e}")
            cursor.execute('UPDATE reviews SET status = "failed" WHERE id = ?', (review_id,))
            # 오류 메시지도 저장
            cursor.execute('UPDATE reviews SET extracted_text = ? WHERE id = ?', (f"Chrome 실행 오류: {str(e)}", review_id))
        
        conn.commit()
        
    except Exception as e:
        print(f"전체 오류: {e}")
    finally:
        conn.close()

@app.get("/delete-review/{review_id}")
async def delete_review(review_id: int):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/delete-store/{store_id}")
async def delete_store(store_id: int):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    # 관련 배정과 리뷰도 함께 삭제
    cursor.execute('DELETE FROM assignments WHERE store_id = ?', (store_id,))
    cursor.execute('DELETE FROM reviews WHERE store_name IN (SELECT name FROM stores WHERE id = ?)', (store_id,))
    cursor.execute('DELETE FROM stores WHERE id = ?', (store_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/delete-user/{username}")
async def delete_user(username: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    # 관련 배정도 함께 삭제
    cursor.execute('DELETE FROM assignments WHERE reviewer_username = ?', (username,))
    cursor.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/extend-store/{company_name}/{store_name}")
def extend_store_form(company_name: str, store_name: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM stores WHERE company_name = ? AND name = ?', (company_name, store_name))
    store = cursor.fetchone()
    conn.close()
    
    if not store:
        return HTMLResponse("업체를 찾을 수 없습니다.")
    
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{store_name} 연장</title>
</head>
<body style="font-family: Arial; background: #f5f7fa; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 100px auto;">
        <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
            <h2 style="margin-bottom: 20px; color: #333; text-align: center;">🔄 {store_name} 연장</h2>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 25px;">
                <h4 style="margin-bottom: 15px; color: #495057;">현재 설정</h4>
                <p style="margin: 5px 0; color: #666;">📅 현재 목표: {(store[4] or 1) * (store[5] or 30)}개 ({store[4] or 1}개/일 × {store[5] or 30}일)</p>
                <p style="margin: 5px 0; color: #666;">📅 현재 기간: {store[3] or '-'}</p>
            </div>
            
            <form action="/submit-extend" method="post">
                <input type="hidden" name="store_name" value="{store_name}">
                <input type="hidden" name="company_name" value="{company_name}">
                
                <div style="margin-bottom: 20px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #555;">추가할 갯수</label>
                    <input name="additional_count" type="number" min="1" value="30" 
                           style="width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 16px;" required>
                    <p style="margin-top: 5px; color: #666; font-size: 12px;">기존 목표에서 추가할 리뷰 갯수를 입력하세요</p>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #555;">연장 사유 (선택)</label>
                    <textarea name="extend_reason" rows="3" placeholder="연장 사유를 입력하세요 (선택사항)"
                              style="width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; resize: vertical;"></textarea>
                </div>
                
                <div style="display: flex; gap: 15px; justify-content: center;">
                    <button type="submit" style="padding: 15px 30px; background: #28a745; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;">🔄 연장하기</button>
                    <a href="/company/{company_name}" style="padding: 15px 30px; background: #6c757d; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">❌ 취소</a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>""")

@app.post("/submit-extend")
async def submit_extend(store_name: str = Form(), company_name: str = Form(), additional_count: int = Form(), extend_reason: str = Form("")):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 현재 목표에서 추가
    cursor.execute('SELECT daily_count, duration_days FROM stores WHERE company_name = ? AND name = ?', (company_name, store_name))
    current = cursor.fetchone()
    
    if current:
        current_total = (current[0] or 1) * (current[1] or 30)
        new_total = current_total + additional_count
        
        # 새로운 일수 계산 (하루 갯수는 유지)
        new_duration = new_total // (current[0] or 1)
        
        cursor.execute('UPDATE stores SET duration_days = ? WHERE company_name = ? AND name = ?', 
                      (new_duration, company_name, store_name))
        conn.commit()
    
    conn.close()
    return RedirectResponse(url=f"/company/{company_name}", status_code=302)

@app.get("/extend-store-admin/{company_name}/{store_name}")
def extend_store_admin_form(company_name: str, store_name: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM stores WHERE company_name = ? AND name = ?', (company_name, store_name))
    store = cursor.fetchone()
    
    # 현재 리뷰 완료 현황
    cursor.execute('SELECT COUNT(*) FROM reviews WHERE store_name = ? AND status = "completed"', (store_name,))
    completed_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM reviews WHERE store_name = ?', (store_name,))
    total_reviews = cursor.fetchone()[0]
    
    conn.close()
    
    if not store:
        return HTMLResponse("업체를 찾을 수 없습니다.")
    
    current_target = (store[4] or 1) * (store[5] or 30)
    
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{store_name} 연장 (관리자)</title>
</head>
<body style="font-family: Arial; background: #f5f7fa; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 100px auto;">
        <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
            <h2 style="margin-bottom: 20px; color: #333; text-align: center;">🔄 {store_name} 연장 설정</h2>
            <p style="text-align: center; color: #666; margin-bottom: 25px;">관리자 권한으로 업체 목표를 연장합니다</p>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 25px;">
                <h4 style="margin-bottom: 15px; color: #495057;">📊 현재 현황</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <p style="margin: 5px 0; color: #666;"><strong>고객사:</strong> {company_name}</p>
                        <p style="margin: 5px 0; color: #666;"><strong>현재 목표:</strong> {current_target}개</p>
                        <p style="margin: 5px 0; color: #666;"><strong>하루 갯수:</strong> {store[4] or 1}개/일</p>
                    </div>
                    <div>
                        <p style="margin: 5px 0; color: #666;"><strong>현재 기간:</strong> {store[5] or 30}일</p>
                        <p style="margin: 5px 0; color: #666;"><strong>완료된 리뷰:</strong> {completed_count}개</p>
                        <p style="margin: 5px 0; color: #666;"><strong>진행률:</strong> {round((completed_count / current_target) * 100) if current_target > 0 else 0}%</p>
                    </div>
                </div>
            </div>
            
            <form action="/submit-extend-admin" method="post">
                <input type="hidden" name="store_name" value="{store_name}">
                <input type="hidden" name="company_name" value="{company_name}">
                
                <div style="margin-bottom: 20px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #555;">추가할 목표 갯수</label>
                    <input name="additional_count" type="number" min="1" value="30" 
                           style="width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 16px;" required>
                    <p style="margin-top: 5px; color: #666; font-size: 12px;">기존 {current_target}개에서 추가할 리뷰 갯수</p>
                </div>
                
                <div style="margin-bottom: 25px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #555;">연장 사유</label>
                    <textarea name="extend_reason" rows="3" placeholder="연장 사유를 입력하세요"
                              style="width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; resize: vertical;" required></textarea>
                </div>
                
                <div style="display: flex; gap: 15px; justify-content: center;">
                    <button type="submit" style="padding: 15px 30px; background: #28a745; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;">🔄 연장 승인</button>
                    <a href="/admin" style="padding: 15px 30px; background: #6c757d; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">❌ 취소</a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>""")

@app.post("/submit-extend-admin")
async def submit_extend_admin(store_name: str = Form(), company_name: str = Form(), additional_count: int = Form(), extend_reason: str = Form()):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    # 현재 설정 가져오기
    cursor.execute('SELECT daily_count, duration_days FROM stores WHERE company_name = ? AND name = ?', (company_name, store_name))
    current = cursor.fetchone()
    
    if current:
        current_total = (current[0] or 1) * (current[1] or 30)
        new_total = current_total + additional_count
        
        # 새로운 일수 계산 (하루 갯수는 유지)
        new_duration = new_total // (current[0] or 1)
        
        cursor.execute('UPDATE stores SET duration_days = ? WHERE company_name = ? AND name = ?', 
                      (new_duration, company_name, store_name))
        conn.commit()
        print(f"업체 연장: {store_name} - {current_total}개 → {new_total}개 (사유: {extend_reason})")
    
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

# 엑셀 업로드 관련 API
from fastapi import UploadFile, File

# 엑셀 템플릿 다운로드
@app.get("/download-template/{template_type}")
async def download_template(template_type: str):
    if template_type == "stores":
        csv_content = "고객사명,업체명,시작일,하루갯수,캠페인일수\n"
        csv_content += "adsketch,황소양곱창 양재점,2024-09-01,5,30\n"
        csv_content += "studioview,쭈꾸미도사 잠실점,2024-09-02,3,20\n"
        filename = "업체등록_템플릿.csv"
    else:  # reviews
        csv_content = "업체명,리뷰URL\n"
        csv_content += "황소양곱창 양재점,https://naver.me/5jBm0HYx\n"
        csv_content += "쭈꾸미도사 잠실점,https://m.place.naver.com/my/review/test\n"
        filename = "리뷰등록_템플릿.csv"
    
    # 한글 파일명 URL 인코딩
    import urllib.parse
    encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
    
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type='text/csv',
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

# 업체 대량 업로드
@app.post("/upload-stores")
async def upload_stores(excel_file: UploadFile = File(...)):
    try:
        contents = await excel_file.read()
        
        if excel_file.filename.endswith('.csv'):
            # CSV 인코딩 문제 해결
            try:
                df = pd.read_csv(io.BytesIO(contents), encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding='cp949')
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(contents), encoding='latin-1')
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        success_count = 0
        error_list = []
        
        for index, row in df.iterrows():
            try:
                company_name = str(row.iloc[0]).strip()
                store_name = str(row.iloc[1]).strip()
                start_date = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                daily_count = int(row.iloc[3]) if pd.notna(row.iloc[3]) else 1
                duration_days = int(row.iloc[4]) if pd.notna(row.iloc[4]) else 30
                
                cursor.execute('SELECT COUNT(*) FROM stores WHERE company_name = ? AND name = ?', (company_name, store_name))
                if cursor.fetchone()[0] == 0:
                    cursor.execute('INSERT INTO stores (company_name, name, start_date, daily_count, duration_days) VALUES (?, ?, ?, ?, ?)',
                                  (company_name, store_name, start_date, daily_count, duration_days))
                    success_count += 1
                else:
                    error_list.append(f"{store_name} (중복)")
                    
            except Exception as e:
                error_list.append(f"행 {index + 2}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>업체 등록 완료</title></head>
<body style="font-family: Arial; text-align: center; padding: 50px;">
    <h2 style="color: #28a745;">✅ 업체 {success_count}개 등록 완료</h2>
    {"<div style='color: #dc3545; margin: 20px 0;'>오류: " + str(len(error_list)) + "개</div>" if error_list else ""}
    <a href="/admin">관리자 페이지로</a>
</body>
</html>""")
        
    except Exception as e:
        return HTMLResponse(f"<h2>업로드 실패: {str(e)}</h2><a href='/admin'>돌아가기</a>")

# 리뷰 대량 업로드
@app.post("/upload-reviews")
async def upload_reviews(excel_file: UploadFile = File(...)):
    try:
        contents = await excel_file.read()
        
        if excel_file.filename.endswith('.csv'):
            # CSV 인코딩 문제 해결
            try:
                df = pd.read_csv(io.BytesIO(contents), encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding='cp949')
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(contents), encoding='latin-1')
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        success_count = 0
        error_list = []
        
        for index, row in df.iterrows():
            try:
                store_name = str(row.iloc[0]).strip()
                review_url = str(row.iloc[1]).strip()
                
                # 업체 존재 확인 (정확한 매칭)
                cursor.execute('SELECT name FROM stores WHERE name = ?', (store_name,))
                exact_match = cursor.fetchone()
                
                matched_store = None
                if exact_match:
                    matched_store = exact_match[0]
                else:
                    # 부분 매칭 시도 (예: "황소양곱창 양재점" → "황소양곱창 양재점 라이징힐즈")
                    cursor.execute('SELECT name FROM stores WHERE name LIKE ?', (f"%{store_name}%",))
                    partial_match = cursor.fetchone()
                    if partial_match:
                        matched_store = partial_match[0]
                        print(f"부분 매칭 성공: '{store_name}' → '{matched_store}'")
                    else:
                        # 역방향 매칭 (예: "황소양곱창 양재점 라이징힐즈" → "황소양곱창 양재점")
                        cursor.execute('SELECT name FROM stores')
                        all_stores = cursor.fetchall()
                        for store_row in all_stores:
                            if store_name in store_row[0]:
                                matched_store = store_row[0]
                                print(f"역방향 매칭 성공: '{store_name}' → '{matched_store}'")
                                break
                
                if not matched_store:
                    cursor.execute('SELECT DISTINCT name FROM stores LIMIT 5')
                    existing_stores = [row[0] for row in cursor.fetchall()]
                    error_list.append(f"{store_name} (업체 없음) - 등록된 업체: {', '.join(existing_stores)}...")
                    continue
                
                # 중복 URL 체크
                cursor.execute('SELECT COUNT(*) FROM reviews WHERE review_url = ?', (review_url,))
                if cursor.fetchone()[0] == 0:
                    cursor.execute('INSERT INTO reviews (store_name, review_url, registered_by, status) VALUES (?, ?, ?, "pending")',
                                  (matched_store, review_url, 'admin'))  # matched_store 사용
                    success_count += 1
                else:
                    error_list.append(f"{review_url[:50]}... (중복 URL)")
                    
            except Exception as e:
                error_list.append(f"행 {index + 2}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        error_details = ""
        if error_list:
            error_details = "<div style='background: #f8d7da; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: left;'>"
            error_details += "<h4 style='color: #721c24; margin-bottom: 15px;'>❌ 오류 상세 내용:</h4>"
            for i, error in enumerate(error_list[:10]):  # 최대 10개만 표시
                error_details += f"<p style='margin: 5px 0; color: #721c24; font-size: 14px;'>{i+1}. {error}</p>"
            if len(error_list) > 10:
                error_details += f"<p style='color: #721c24;'>... 외 {len(error_list) - 10}개 더</p>"
            error_details += "</div>"
        
        return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>리뷰 등록 결과</title></head>
<body style="font-family: Arial; padding: 20px;">
    <div style="max-width: 800px; margin: 0 auto; text-align: center;">
        <h2 style="color: #007bff;">📊 리뷰 등록 결과</h2>
        <div style="background: #d4edda; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #155724;">✅ 성공: {success_count}개</h3>
        </div>
        <div style="background: #f8d7da; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #721c24;">❌ 실패: {len(error_list)}개</h3>
        </div>
        {error_details}
        <a href="/admin?tab=upload" style="padding: 15px 30px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">엑셀업로드 탭으로</a>
    </div>
</body>
</html>""")
        
    except Exception as e:
        return HTMLResponse(f"<h2>업로드 실패: {str(e)}</h2><a href='/admin'>돌아가기</a>")

@app.get("/api/store-reviews/{store_name}")
async def get_store_reviews(store_name: str):
    """특정 업체의 리뷰 목록 반환 (날짜순 정렬)"""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, store_name, review_url, extracted_text, extracted_date, status, registered_by, created_at
        FROM reviews 
        WHERE store_name = ? 
        ORDER BY 
            CASE 
                WHEN extracted_date IS NOT NULL AND extracted_date != '' THEN extracted_date 
                ELSE created_at 
            END DESC
    ''', (store_name,))
    
    reviews = cursor.fetchall()
    conn.close()
    
    return [{
        "id": r[0],
        "store_name": r[1], 
        "review_url": r[2],
        "extracted_text": r[3],
        "extracted_date": r[4],
        "status": r[5],
        "registered_by": r[6],
        "created_at": r[7]
    } for r in reviews]

@app.get("/retry-review/{review_id}")
async def retry_review(review_id: int, background_tasks: BackgroundTasks):
    # 실패한 리뷰를 pending 상태로 되돌리고 재추출
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('UPDATE reviews SET status = "pending" WHERE id = ?', (review_id,))
    conn.commit()
    conn.close()
    
    # 백그라운드에서 재추출
    background_tasks.add_task(extract_review, review_id)
    
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>재시도 시작</title></head>
<body style="font-family: Arial; background: #f5f7fa; text-align: center; padding: 50px;">
    <div style="background: white; padding: 40px; border-radius: 15px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
        <h2 style="color: #ffc107; margin-bottom: 20px;">🔄 리뷰 재추출 시작!</h2>
        <p style="margin-bottom: 15px; font-size: 16px;">실패한 리뷰의 재추출을 시작합니다.</p>
        <p style="margin-bottom: 25px; color: #666;">다른 방법으로 리뷰 내용을 찾아보겠습니다.</p>
        <div style="margin-bottom: 25px; padding: 15px; background: #fff3cd; border-radius: 8px;">
            <p style="margin: 0; color: #856404; font-weight: 600;">⏰ 약 30초 후 결과를 확인하세요</p>
        </div>
        <a href="/admin?tab=reviews" style="padding: 15px 30px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">리뷰 관리 탭으로</a>
    </div>
</body>
</html>""")

# 관리자 권한 체크 함수 (쿠키 방식)
async def get_admin_user(request: Request):
    """관리자 권한 확인 - 쿠키 기반"""
    username = request.cookies.get('username')
    if username == 'admin':
        return {"username": "admin", "role": "admin"}
    
    # admin이 아니면 로그인 페이지로 리다이렉트
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=302)

# ==================== 영수증 생성기 라우트 ====================

@app.get("/admin/receipt-generator")
async def receipt_generator_page(request: Request):
    """관리자 전용 영수증생성기 페이지"""
    # 쿠키로 관리자 확인
    username = request.cookies.get('username')
    if username != 'admin':
        return RedirectResponse(url="/", status_code=302)
    
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>영수증 생성기 - 관리자 전용</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 800px; margin: 0 auto; padding: 20px; }
            .card { background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); padding: 30px; margin-bottom: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .header h1 { color: #333; font-size: 2.5em; margin-bottom: 10px; }
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; font-weight: 600; color: #555; }
            .form-control { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; transition: border-color 0.3s; }
            .form-control:focus { border-color: #667eea; outline: none; }
            textarea.form-control { min-height: 120px; font-family: monospace; }
            .btn { background: linear-gradient(45deg, #667eea, #764ba2); color: white; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s; }
            .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
            .btn-secondary { background: linear-gradient(45deg, #28a745, #20c997); margin-right: 10px; }
            .result { margin-top: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #28a745; }
            .nav-link { color: white; text-decoration: none; padding: 10px 20px; background: rgba(255,255,255,0.2); border-radius: 8px; display: inline-block; margin-bottom: 20px; }
            .nav-link:hover { background: rgba(255,255,255,0.3); }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="nav-link">← 메인으로 돌아가기</a>
            
            <div class="card">
                <div class="header">
                    <h1>🧾 영수증 생성기</h1>
                    <p>관리자 전용 - 네이버 플레이스 메뉴 기반 영수증 생성</p>
                </div>

                <form id="receiptForm">
                    <div class="form-group">
                        <label>네이버 플레이스 URL (선택사항)</label>
                        <input type="url" class="form-control" id="placeUrl" placeholder="https://place.naver.com/restaurant/1234567890">
                        <button type="button" class="btn btn-secondary" onclick="fetchMenu()" style="margin-top: 10px;">메뉴 자동 추출</button>
                    </div>

                    <div class="form-group">
                        <label>상호명 *</label>
                        <input type="text" class="form-control" id="storeName" placeholder="예: 맛있는 식당" required>
                    </div>

                    <div class="form-group">
                        <label>메뉴 정보 * (메뉴명 가격 형식으로 입력)</label>
                        <textarea class="form-control" id="menuText" placeholder="김치찌개 8000원
된장찌개 7000원
불고기정식 12000원" required></textarea>
                    </div>

                    <div class="form-group">
                        <label>생성할 영수증 개수</label>
                        <input type="number" class="form-control" id="receiptCount" value="10" min="1" max="50">
                    </div>

                    <div class="form-group">
                        <label>날짜 범위 (최근 며칠)</label>
                        <input type="number" class="form-control" id="dateRange" value="30" min="1" max="365">
                    </div>

                    <button type="submit" class="btn">🎯 영수증 생성하기</button>
                </form>

                <div id="result" style="display: none;"></div>
            </div>
        </div>

        <script>
            async function fetchMenu() {
                const placeUrl = document.getElementById('placeUrl').value;
                if (!placeUrl) {
                    alert('네이버 플레이스 URL을 입력해주세요.');
                    return;
                }

                try {
                    const response = await fetch('/admin/api/fetch-menu', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ place_url: placeUrl })
                    });

                    const data = await response.json();
                    
                    if (data.success) {
                        document.getElementById('storeName').value = data.store_name;
                        document.getElementById('menuText').value = data.menu_text;
                        alert(`메뉴 ${data.total_count}개를 성공적으로 추출했습니다!`);
                    } else {
                        alert(`오류: ${data.error}`);
                    }
                } catch (error) {
                    alert(`네트워크 오류: ${error.message}`);
                }
            }

            document.getElementById('receiptForm').onsubmit = async function(e) {
                e.preventDefault();
                
                const formData = {
                    store_name: document.getElementById('storeName').value,
                    menu_text: document.getElementById('menuText').value,
                    receipt_count: parseInt(document.getElementById('receiptCount').value),
                    date_range: parseInt(document.getElementById('dateRange').value)
                };

                try {
                    const response = await fetch('/admin/api/generate-receipts', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });

                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `receipts_${formData.store_name}_${new Date().getTime()}.zip`;
                        a.click();
                        window.URL.revokeObjectURL(url);

                        document.getElementById('result').innerHTML = `
                            <h3>✅ 영수증 생성 완료!</h3>
                            <p><strong>${formData.receipt_count}개</strong>의 영수증이 생성되어 다운로드되었습니다.</p>
                        `;
                        document.getElementById('result').style.display = 'block';
                    } else {
                        const error = await response.json();
                        alert(`오류: ${error.detail}`);
                    }
                } catch (error) {
                    alert(`오류: ${error.message}`);
                }
            };
        </script>
    </body>
    </html>
    """)

@app.post("/admin/api/fetch-menu")
async def fetch_menu(request: Request):
    """네이버 플레이스에서 메뉴 추출 API"""
    # 임시로 권한 체크 비활성화 (테스트용)
    # username = request.cookies.get('username')
    # if username != 'admin':
    #     raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    data = await request.json()
    place_url = data.get('place_url')
    
    if not place_url:
        raise HTTPException(status_code=400, detail="네이버 플레이스 URL이 필요합니다")
    
    try:
        result = get_naver_place_menu(place_url)
        
        if result.get('success'):
            menu_text = format_menu_for_textarea(result)
            return {
                "success": True,
                "store_name": result.get('store_name', ''),
                "menu_text": menu_text,
                "total_count": result.get('total_count', 0)
            }
        else:
            return {"success": False, "error": result.get('error', '알 수 없는 오류')}
            
    except Exception as e:
        return {"success": False, "error": f"서버 오류: {str(e)}"}

@app.post("/admin/api/generate-receipts")
async def generate_receipts(request: Request):
    """영수증 생성 및 ZIP 다운로드 API"""
    # 관리자 확인
    username = request.cookies.get('username')
    if username != 'admin':
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    data = await request.json()
    
    store_name = data.get('store_name', '').strip()
    menu_text = data.get('menu_text', '').strip()
    receipt_count = data.get('receipt_count', 10)
    date_range = data.get('date_range', 30)
    
    if not store_name or not menu_text:
        raise HTTPException(status_code=400, detail="상호명과 메뉴 정보는 필수입니다")
    
    try:
        # 메뉴 파싱
        menu_pool = parse_menu_input(menu_text, apply_filter=True)
        
        if not menu_pool:
            raise HTTPException(status_code=400, detail="유효한 메뉴 정보를 찾을 수 없습니다")
        
        # 영수증 생성
        receipts = generate_receipts_batch_web(
            store_name=store_name,
            menu_pool=menu_pool,
            count=receipt_count,
            date_range_days=date_range
        )
        
        # ZIP 파일 생성
        zip_buffer = create_receipts_zip(receipts)
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            tmp_file.write(zip_buffer.getvalue())
            tmp_file_path = tmp_file.name
        
        return FileResponse(
            path=tmp_file_path,
            filename=f"receipts_{store_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            media_type='application/zip'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"영수증 생성 오류: {str(e)}")

@app.post("/admin/api/generate-receipts-full")
async def generate_receipts_full(request: Request):
    """완전한 영수증 생성 API (날짜 범위, 업체 정보 포함)"""
    # 관리자 확인 (쿠키 디버깅)
    username = request.cookies.get('username')
    print(f"DEBUG: 쿠키에서 읽은 username: {username}")
    
    # 임시로 권한 체크 비활성화 (테스트용)
    # if username != 'admin':
    #     raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    data = await request.json()
    
    # 필수 데이터 추출
    store_name = data.get('store_name', '').strip()
    biz_num = data.get('biz_num', '').strip()
    owner_name = data.get('owner_name', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()
    menu_text = data.get('menu_text', '').strip()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    daily_count = data.get('daily_count', 5)
    start_hour = data.get('start_hour', 11)
    end_hour = data.get('end_hour', 21)
    apply_filter = data.get('apply_filter', True)
    
    if not all([store_name, biz_num, owner_name, phone, address, menu_text, start_date, end_date]):
        raise HTTPException(status_code=400, detail="모든 필수 항목을 입력해주세요")
    
    try:
        from datetime import datetime, timedelta
        import random
        
        # 업체 정보 구성 (새로운 방식)
        store_info = {
            '상호명': store_name,
            '사업자번호': biz_num,
            '대표자명': owner_name,
            '전화번호': phone,
            '주소': address
        }
        
        # 메뉴 파싱
        menu_pool = parse_menu_input(menu_text, apply_filter=apply_filter)
        
        if not menu_pool:
            raise HTTPException(status_code=400, detail="유효한 메뉴 정보를 찾을 수 없습니다")
        
        # 날짜 범위 계산
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # 기존 방식 유지 (안정성 우선)
        receipts = []
        current_date = start_dt
        
        while current_date <= end_dt:
            for _ in range(daily_count):
                # 랜덤 시간 생성
                hour = random.randint(start_hour, end_hour)
                minute = random.randint(0, 59)
                receipt_datetime = current_date.replace(hour=hour, minute=minute)
                
                # 랜덤 메뉴 선택
                selected_menus = random.sample(menu_pool, min(random.randint(1, 3), len(menu_pool)))
                total_amount = sum(price for _, price in selected_menus)
                
                # 기존의 단순한 영수증 생성 방식 사용
                receipt_img = create_receipt_image_full(
                    store_name, biz_num, owner_name, phone, address,
                    selected_menus, total_amount, receipt_datetime
                )
                
                # 이미지를 바이트로 변환
                img_byte_arr = io.BytesIO()
                receipt_img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                receipts.append({
                    'filename': f'receipt_{receipt_datetime.strftime("%Y%m%d_%H%M%S")}_{len(receipts)+1:03d}.png',
                    'image_data': img_byte_arr.getvalue(),
                    'date': receipt_datetime,
                    'total': total_amount,
                    'menus': selected_menus
                })
            
            current_date += timedelta(days=1)
        
        # 기존 ZIP 생성 방식 사용
        zip_buffer = create_receipts_zip(receipts)
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            tmp_file.write(zip_buffer.getvalue())
            tmp_file_path = tmp_file.name
        
        return FileResponse(
            path=tmp_file_path,
            filename=f"receipts_{store_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            media_type='application/zip'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"영수증 생성 오류: {str(e)}")

# ==================== 고급 영수증 생성기 API ====================

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
ALLOWED_EXCEL_EXTENSIONS = {'xlsx', 'xls', 'csv'}

@app.post("/api/generate_advanced_receipts")
async def generate_advanced_receipts(
    # 업체 정보
    store_name: str = Form(...),
    biz_num: str = Form(...),
    owner_name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    
    # 메뉴 및 생성 정보
    menu_list: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    daily_count: int = Form(...),
    start_hour: int = Form(11),
    end_hour: int = Form(21),
    apply_menu_filter: bool = Form(True),
    
    # 엑셀 파일 (선택)
    use_excel: bool = Form(False),
    excel_file: Optional[UploadFile] = File(None),
    
    # 사진 파일들 (선택)
    photos: List[UploadFile] = File([]),
    
    # 텍스트 내용 (선택)
    text_content: str = Form(""),
):
    """고급 영수증 생성 API - 사진, 엑셀, 리뷰 통합"""
    try:
        print("\n" + "="*50)
        print("[DEBUG] 고급 영수증 생성 요청 시작")
        print("="*50)
        
        # 업체 정보 구성
        store_info = {
            '상호명': store_name,
            '사업자번호': biz_num,
            '대표자명': owner_name,
            '전화번호': phone,
            '주소': address
        }
        
        # 메뉴 파싱
        menu_pool = parse_menu_input(menu_list, apply_filter=apply_menu_filter)
        
        # 날짜 정보
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        
        print(f"[DEBUG] 날짜 범위: {start_date_obj} ~ {end_date_obj}")
        print(f"[DEBUG] 일일 생성 개수: {daily_count}")
        
        # 영수증 생성
        receipt_results = generate_receipts_batch_web(
            store_info, menu_pool, start_date_obj, end_date_obj, 
            daily_count, start_hour, end_hour
        )
        
        print(f"[DEBUG] 생성된 영수증 개수: {len(receipt_results)}")
        
        # 사진 처리
        photo_images = []
        if photos:
            print(f"[DEBUG] 업로드된 사진 수: {len(photos)}")
            
            for idx, photo in enumerate(photos):
                if photo and photo.filename and allowed_file(photo.filename, ALLOWED_IMAGE_EXTENSIONS):
                    contents = await photo.read()
                    clean_img = remove_image_metadata(io.BytesIO(contents))
                    if clean_img:
                        photo_images.append(clean_img)
                        print(f"[DEBUG] 사진 {idx+1} 처리 완료")
        
        # 엑셀 데이터 처리
        excel_data = {}
        if use_excel and excel_file and excel_file.filename:
            if allowed_file(excel_file.filename, ALLOWED_EXCEL_EXTENSIONS):
                # 임시 파일로 저장
                temp_path = f"temp_{secure_filename(excel_file.filename)}"
                contents = await excel_file.read()
                
                with open(temp_path, 'wb') as f:
                    f.write(contents)
                
                try:
                    # 엑셀 파싱
                    excel_items = parse_excel_file(temp_path)
                    # 번호를 키로 하는 딕셔너리로 변환
                    for item in excel_items:
                        excel_data[item['번호']] = item
                    print(f"[DEBUG] 엑셀 데이터 {len(excel_data)}개 로드")
                except Exception as e:
                    print(f"[ERROR] 엑셀 파싱 실패: {str(e)}")
                finally:
                    # 임시 파일 삭제
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
        
        # 텍스트 처리
        text_files_list = []
        if not use_excel and text_content.strip():
            text_files_dict = parse_text_to_files(text_content)
            text_files_list = [(content, filename) for filename, content in text_files_dict.items()]
            print(f"[DEBUG] 텍스트 파싱: {len(text_files_list)}개")
        
        # 전체 zip 파일 생성
        master_zip = io.BytesIO()
        
        with zipfile.ZipFile(master_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            receipt_number = 1
            
            for idx, (receipt_img, receipt_path) in enumerate(receipt_results):
                # 경로 정보 추출
                path_parts = receipt_path.split('/')
                date_str = path_parts[1] if len(path_parts) > 1 else ""
                
                # 순번으로 파일명 생성
                receipt_num_str = f"{receipt_number:03d}"
                
                # 엑셀 데이터 확인
                excel_item = excel_data.get(receipt_number, {})
                review_content = excel_item.get('리뷰내용', '')
                has_review = bool(review_content and str(review_content).strip())
                photo_num = excel_item.get('사진번호')
                
                # 사진번호를 정수로 변환
                try:
                    photo_num = int(photo_num) if photo_num else None
                except (ValueError, TypeError):
                    photo_num = None
                has_photo = photo_num and photo_num <= len(photo_images) if photo_num else False
                
                print(f"[DEBUG] 영수증 {receipt_num_str}: 엑셀데이터={bool(excel_item)}, 리뷰내용='{review_content}', has_review={has_review}, 사진번호={photo_num}, 사진유무={has_photo}")
                
                # 패키지 생성 여부 결정
                if has_review or has_photo:
                    # 압축 파일 생성
                    package_zip = io.BytesIO()
                    
                    with zipfile.ZipFile(package_zip, 'w', zipfile.ZIP_DEFLATED) as pkg_zip:
                        # 영수증 추가
                        receipt_img.seek(0)
                        pkg_zip.writestr('영수증.jpg', receipt_img.read())
                        
                        # 사진 추가
                        if has_photo:
                            photo_idx = photo_num - 1  # 0부터 시작하는 인덱스
                            photo_buffer = photo_images[photo_idx]
                            photo_buffer.seek(0)
                            pkg_zip.writestr('사진.jpg', photo_buffer.read())
                        
                        # 리뷰 추가
                        if has_review:
                            review_text = str(excel_item['리뷰내용']).strip()
                            pkg_zip.writestr('리뷰.txt', review_text.encode('utf-8'))
                            print(f"[DEBUG] 리뷰 추가됨: {review_text[:50]}...")
                    
                    package_zip.seek(0)
                    
                    # 압축파일 추가
                    package_filename = f"{store_info['상호명']}_{date_str}_{receipt_num_str}.zip"
                    zip_path = f"{store_info['상호명']}/{date_str}/{package_filename}"
                    zip_file.writestr(zip_path, package_zip.read())
                    
                    content_list = []
                    if has_review:
                        content_list.append("리뷰")
                    if has_photo:
                        content_list.append(f"사진{photo_num}")
                    print(f"[DEBUG] 패키지 생성: {zip_path} ({'+'.join(content_list)})")
                    
                else:
                    # 영수증만 추가
                    receipt_img.seek(0)
                    # 파일명에 순번 추가
                    filename = path_parts[-1].rsplit('.', 1)[0] + f"_{receipt_num_str}.jpg"
                    new_path = f"{path_parts[0]}/{path_parts[1]}/{filename}"
                    zip_file.writestr(new_path, receipt_img.read())
                    print(f"[DEBUG] 영수증만: {new_path}")
                
                receipt_number += 1
        
        master_zip.seek(0)
        
        print(f"[DEBUG] 전체 압축 파일 생성 완료")
        
        # ZIP 파일 반환
        filename = f"{store_info['상호명']}_영수증_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        return StreamingResponse(
            io.BytesIO(master_zip.read()),
            media_type='application/zip',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        import traceback
        print(f"[ERROR] 고급 영수증 생성 오류: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"영수증 생성 오류: {str(e)}")

@app.get("/api/get_naver_menu")
async def get_naver_menu_api(url: str):
    """네이버 플레이스 메뉴 추출 API"""
    try:
        if not url or 'naver.com' not in url:
            raise HTTPException(status_code=400, detail='유효한 네이버 플레이스 URL을 입력해주세요.')
        
        # 메뉴 추출 (리스트 반환)
        menu_items = get_naver_place_menu(url)
        print(f"[DEBUG] 추출된 메뉴 타입: {type(menu_items)}")
        print(f"[DEBUG] 추출된 메뉴: {menu_items}")
        
        # 7글자 필터 적용
        menu_text = format_menu_for_textarea(menu_items, apply_filter=True)
        
        return {
            'success': True,
            'menu_text': menu_text,
            'count': len(menu_text.split('\n')) if menu_text else 0
        }
        
    except Exception as e:
        print(f"[ERROR] 메뉴 추출 API 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("리뷰 관리 시스템 + 영수증 생성기")
    print("접속: http://localhost:8000")
    print("영수증 생성기: http://localhost:8000/admin/receipt-generator (관리자만)")
    print("고급 영수증 생성기 API: POST /api/generate_advanced_receipts")
    print("네이버 메뉴 추출 API: GET /api/get_naver_menu?url=...")
    print("단일 로그인: 사용자명만 입력하면 자동 등급 인식")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")