from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import uvicorn
import sqlite3
import hashlib
import os
import re
from datetime import datetime, timedelta

app = FastAPI()

def init_db():
    if os.path.exists('clean.db'):
        os.remove('clean.db')
    
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    
    # 사용자 테이블 (모든 사용자를 하나의 테이블에)
    cursor.execute('''CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        user_type TEXT,
        company_name TEXT
    )''')
    
    # 업체 테이블
    cursor.execute('''CREATE TABLE stores (
        id INTEGER PRIMARY KEY,
        company_name TEXT,
        name TEXT,
        start_date TEXT,
        daily_count INTEGER,
        duration_days INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 배정 테이블
    cursor.execute('''CREATE TABLE assignments (
        id INTEGER PRIMARY KEY,
        reviewer_username TEXT,
        store_id INTEGER
    )''')
    
    # 리뷰 테이블
    cursor.execute('''CREATE TABLE reviews (
        id INTEGER PRIMARY KEY,
        store_name TEXT,
        review_url TEXT,
        extracted_text TEXT,
        extracted_date TEXT,
        status TEXT DEFAULT 'pending',
        registered_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 관리자 계정만 생성 (실제 서버용)
    admin_hash = hashlib.sha256("doemtmzpcl1!".encode()).hexdigest()
    cursor.execute('INSERT INTO users (username, password_hash, user_type) VALUES (?, ?, ?)', ('admin', admin_hash, 'admin'))
    
    conn.commit()
    conn.close()

init_db()

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
            <h1 style="margin-bottom: 30px; color: #333;">네이버 리뷰 관리 시스템</h1>
            
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
    conn = sqlite3.connect('clean.db')
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
    conn = sqlite3.connect('clean.db')
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
                end = start + timedelta(days=(s[5] or 30) - 1)
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
        
        reviews_html += f'''<div style="padding: 12px; border-bottom: 1px solid #eee;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                <div>
                    <strong>{r[1]}</strong>
                    <span style="margin-left: 10px; padding: 2px 6px; background: {status_color}; color: white; border-radius: 8px; font-size: 10px;">{status_text}</span>
                    <span style="margin-left: 10px; color: #666; font-size: 12px;">{r[6]}</span>
                    {date_info}
                </div>
                <div style="display: flex; gap: 5px;">
                    {process_button}
                    <a href="/delete-review/{r[0]}" onclick="return confirm('이 리뷰를 삭제하시겠습니까?')" style="padding: 4px 8px; background: #dc3545; color: white; text-decoration: none; border-radius: 3px; font-size: 11px;">🗑️</a>
                </div>
            </div>
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
            ['companies', 'stores', 'reviewers', 'assignments', 'reviews'].forEach(t => {{
                document.getElementById(t + 'Tab').style.display = t === tab ? 'block' : 'none';
                document.getElementById(t + 'Btn').style.background = t === tab ? '#4285f4' : '#f8f9fa';
                document.getElementById(t + 'Btn').style.color = t === tab ? 'white' : '#333';
            }});
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
                <button onclick="showTab('companies')" id="companiesBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #4285f4; color: white; cursor: pointer; font-weight: 600;">🏢 고객사</button>
                <button onclick="showTab('stores')" id="storesBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">🏪 업체</button>
                <button onclick="showTab('reviewers')" id="reviewersBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">👤 리뷰어</button>
                <button onclick="showTab('assignments')" id="assignmentsBtn" style="padding: 12px 24px; margin-right: 8px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">🔗 배정</button>
                <button onclick="showTab('reviews')" id="reviewsBtn" style="padding: 12px 24px; border: none; border-radius: 8px 8px 0 0; background: #f8f9fa; color: #333; cursor: pointer; font-weight: 600;">📝 리뷰</button>
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
        </div>
    </div>
</body>
</html>""")

@app.get("/company/{company_name}")
def company_page(company_name: str):
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    
    # 해당 고객사의 업체들
    cursor.execute('SELECT * FROM stores WHERE company_name = ? ORDER BY created_at DESC', (company_name,))
    stores = cursor.fetchall()
    
    # 해당 고객사의 완료된 리뷰들
    cursor.execute('''
        SELECT r.* FROM reviews r
        JOIN stores s ON r.store_name = s.name
        WHERE s.company_name = ? AND r.status = "completed"
        ORDER BY r.created_at DESC
    ''', (company_name,))
    completed_reviews = cursor.fetchall()
    
    # 전체 리뷰 (상태별 통계용)
    cursor.execute('''
        SELECT r.* FROM reviews r
        JOIN stores s ON r.store_name = s.name
        WHERE s.company_name = ?
    ''', (company_name,))
    all_reviews = cursor.fetchall()
    
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
                end = start + timedelta(days=(s[5] or 30) - 1)
                end_date = end.strftime('%Y-%m-%d')
            except:
                end_date = ''
        
        total_target = (s[4] or 1) * (s[5] or 30)
        store_completed = len([r for r in completed_reviews if r[1] == s[2]])
        store_total = len([r for r in all_reviews if r[1] == s[2]])
        percentage = round((store_completed / total_target) * 100) if total_target > 0 else 0
        
        # 상태 판정
        if store_completed >= total_target:
            status = '완료'
            status_color = '#28a745'
            card_class = 'completed-store'
        elif store_total > 0:
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
                    <a href="/download-store-csv/{company_name}/{s[2]}" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 600;">📊 업체별 리포트</a>
                </div>
            </div>
            <div style="margin-bottom: 10px; color: #666; font-size: 14px;">
                📅 <strong>기간:</strong> {s[3] or '-'} ~ {end_date or '-'} ({s[5] or 30}일)
            </div>
            <div style="margin-bottom: 10px; color: #666; font-size: 14px;">
                🎯 <strong>목표:</strong> {total_target}개 ({s[4] or 1}개/일 × {s[5] or 30}일)
            </div>
            <div style="font-size: 20px; font-weight: bold; color: {status_color};">
                📊 {store_completed}/{total_target} ({percentage}%)
            </div>
        </div>'''
        
        search_options += f'<option value="{s[2]}">{s[2]}</option>'
    
    if not stores_html:
        stores_html = '<p style="color: #999; text-align: center; padding: 40px;">등록된 업체가 없습니다</p>'
    
    # 완료된 리뷰 테이블
    reviews_table = ''
    if completed_reviews:
        reviews_table = '''
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <thead style="background: #f8f9fa;">
                <tr>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">업체명</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">리뷰URL</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">리뷰내용</th>
                    <th style="padding: 12px; border: 1px solid #ddd; font-weight: 600;">영수증날짜</th>
                </tr>
            </thead>
            <tbody id="reviewsTable">'''
        
        for r in completed_reviews:
            reviews_table += f'''
                <tr class="review-row" data-store="{r[1]}">
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: 600;">{r[1]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-size: 11px;"><a href="{r[2]}" target="_blank" style="color: #007bff;">{r[2][:35]}...</a></td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px; line-height: 1.4;">{r[3] or '-'}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: 600; color: #dc3545;">{r[4] or '-'}</td>
                </tr>'''
        
        reviews_table += '</tbody></table>'
    else:
        reviews_table = '<p style="text-align: center; padding: 40px; color: #999;">완료된 리뷰가 없습니다</p>'
    
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
            </script>
            
            <!-- 완료된 리뷰 목록 -->
            <div>
                <h4 style="margin-bottom: 15px; color: #495057;">✅ 완료된 리뷰 목록 (업체용 리포트)</h4>
                {reviews_table}
            </div>
        </div>
    </div>
</body>
</html>""")

# API들
@app.post("/create-company")
async def create_company(name: str = Form(), password: str = Form()):
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute('INSERT INTO users (username, password_hash, user_type, company_name) VALUES (?, ?, ?, ?)', 
                  (name, password_hash, 'company', name))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.post("/create-store")
async def create_store(company_name: str = Form(), name: str = Form(), start_date: str = Form(""), daily_count: int = Form(1), duration_days: int = Form(30)):
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO stores (company_name, name, start_date, daily_count, duration_days) VALUES (?, ?, ?, ?, ?)',
                  (company_name, name, start_date, daily_count, duration_days))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.post("/create-reviewer")
async def create_reviewer(name: str = Form(), password: str = Form()):
    conn = sqlite3.connect('clean.db')
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
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO assignments (reviewer_username, store_id) VALUES (?, ?)', 
                  (reviewer_username, store_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/download-csv/{company_name}")
async def download_csv(company_name: str):
    conn = sqlite3.connect('clean.db')
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
    
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type='application/octet-stream',
        headers={"Content-Disposition": f"attachment; filename={company_name}_report.csv"}
    )

@app.get("/download-store-csv/{company_name}/{store_name}")
async def download_store_csv(company_name: str, store_name: str):
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.store_name, r.review_url, r.extracted_text, r.extracted_date
        FROM reviews r
        WHERE r.store_name = ? AND r.status = "completed"
        ORDER BY r.created_at
    ''', (store_name,))
    
    reviews = cursor.fetchall()
    conn.close()
    
    csv_content = f"{store_name} 리뷰 현황 보고서\n"
    csv_content += f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    csv_content += f"완료된 리뷰: {len(reviews)}개\n"
    csv_content += "\n"
    csv_content += "업체명,리뷰URL,리뷰내용,영수증날짜\n"
    
    for r in reviews:
        content = (r[2] or "").replace('"', '""')
        csv_content += f'"{r[0]}","{r[1]}","{content}","{r[3] or ""}"\n'
    
    # 안전한 파일명 생성 (영문+숫자만)
    safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', store_name)
    
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type='application/octet-stream',
        headers={"Content-Disposition": f"attachment; filename={safe_filename}.csv"}
    )

@app.get("/reviewer/{reviewer_name}")
def reviewer_page(reviewer_name: str):
    conn = sqlite3.connect('clean.db')
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
    
    # 배정된 업체 HTML
    stores_html = ''
    for s in assigned_stores:
        my_store_reviews = len([r for r in my_reviews if r[1] == s[2]])
        stores_html += f'''
        <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #007bff;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div>
                    <h4 style="margin: 0; color: #333; font-size: 18px;">{s[2]}</h4>
                </div>
                <a href="/add-review-form/{reviewer_name}/{s[2]}" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">+ 리뷰 추가</a>
            </div>
            <div style="color: #666; font-size: 14px;">
                📊 내가 등록한 리뷰: {my_store_reviews}개
            </div>
        </div>'''
    
    if not stores_html:
        stores_html = '<p style="color: #999; text-align: center; padding: 40px;">배정된 업체가 없습니다. 관리자에게 업체 배정을 요청하세요.</p>'
    
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
        
        <div style="background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 25px; margin-bottom: 25px;">
            <h3 style="margin-bottom: 20px; color: #333;">🏪 담당 업체 목록</h3>
            {stores_html}
        </div>
        
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
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reviews (store_name, review_url, registered_by, status) VALUES (?, ?, ?, "pending")',
                  (store_name, review_url, registered_by))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/reviewer/{registered_by}", status_code=302)

@app.get("/process-all")
async def process_all(background_tasks: BackgroundTasks):
    conn = sqlite3.connect('clean.db')
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
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    
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
    conn = sqlite3.connect('clean.db')
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
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            # headless 모드 제거하여 Chrome 창이 보이도록 함
            
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(5)
            driver.get(review_url)
            
            if "/my/review/" in review_url:
                # 직접 리뷰 링크
                time.sleep(3)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                review_elem = soup.find('a', {'data-pui-click-code': 'reviewend.text'})
                text = review_elem.get_text(strip=True) if review_elem else "리뷰 본문을 찾을 수 없습니다"
                
                time_elem = soup.find('time', {'aria-hidden': 'true'})
                date = time_elem.get_text(strip=True) if time_elem else "영수증 날짜를 찾을 수 없습니다"
                
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
                    
                    time_elem = target_review.find('time', {'aria-hidden': 'true'})
                    date = time_elem.text.strip() if time_elem else "영수증 날짜를 찾을 수 없습니다"
                    
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
            
            # 결과 저장
            status = 'completed' if "찾을 수 없습니다" not in text and len(text) > 10 else 'failed'
            cursor.execute('UPDATE reviews SET status = ?, extracted_text = ?, extracted_date = ? WHERE id = ?',
                          (status, text, date, review_id))
            
            print(f"추출 완료: {store_name} - {status}")
            
        except Exception as e:
            print(f"추출 실패: {e}")
            cursor.execute('UPDATE reviews SET status = "failed" WHERE id = ?', (review_id,))
        
        conn.commit()
        
    except Exception as e:
        print(f"전체 오류: {e}")
    finally:
        conn.close()

@app.get("/delete-review/{review_id}")
async def delete_review(review_id: int):
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/delete-store/{store_id}")
async def delete_store(store_id: int):
    conn = sqlite3.connect('clean.db')
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
    conn = sqlite3.connect('clean.db')
    cursor = conn.cursor()
    # 관련 배정도 함께 삭제
    cursor.execute('DELETE FROM assignments WHERE reviewer_username = ?', (username,))
    cursor.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=302)

@app.get("/extend-store/{company_name}/{store_name}")
def extend_store_form(company_name: str, store_name: str):
    conn = sqlite3.connect('clean.db')
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
    conn = sqlite3.connect('clean.db')
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
    conn = sqlite3.connect('clean.db')
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
    conn = sqlite3.connect('clean.db')
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

if __name__ == "__main__":
    print("깔끔한 네이버 리뷰 관리 시스템")
    print("접속: http://localhost:8000")
    print("단일 로그인: 사용자명만 입력하면 자동 등급 인식")
    uvicorn.run(app, host="0.0.0.0", port=8000)