# 영수증 시스템 공통 유틸리티 함수들

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os

def remove_image_metadata(image_file):
    """이미지 파일의 모든 메타데이터 제거"""
    from PIL import Image
    import io
    
    try:
        # 이미지 열기 (파일 객체 또는 경로 모두 지원)
        img = Image.open(image_file)
        
        # RGB로 변환 (RGBA나 P 모드의 경우)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # 새로운 이미지로 저장 (메타데이터 없이)
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=95)
        output.seek(0)
        
        return output
    except Exception as e:
        print(f"[ERROR] 메타데이터 제거 실패: {str(e)}")
        return None

def parse_text_to_files(text_content):
    """텍스트 내용을 개별 파일로 분리
    형식: 숫자. 원고 내용
    """
    import re
    
    files = {}
    
    # 줄바꿈으로 분리
    lines = text_content.strip().split('\n')
    current_number = None
    current_content = []
    
    for line in lines:
        # 숫자. 으로 시작하는 라인 찾기
        match = re.match(r'^(\d+)\.\s*(.*)$', line.strip())
        if match:
            # 이전 번호의 내용 저장
            if current_number is not None:
                filename = f"{current_number}.txt"
                files[filename] = '\n'.join(current_content).strip()
            
            # 새로운 번호 시작
            current_number = match.group(1)
            content = match.group(2)
            current_content = [content] if content else []
        else:
            # 현재 번호의 내용에 추가
            if current_number is not None and line.strip():
                current_content.append(line.strip())
    
    # 마지막 번호의 내용 저장
    if current_number is not None:
        filename = f"{current_number}.txt"
        files[filename] = '\n'.join(current_content).strip()
    
    return files

def validate_file_upload(file, allowed_extensions=None):
    """파일 업로드 유효성 검증"""
    if allowed_extensions is None:
        allowed_extensions = ('.xlsx', '.xls', '.csv')
    
    if not file or file.filename == '':
        return False, '파일이 선택되지 않았습니다.'
    
    if not file.filename.lower().endswith(allowed_extensions):
        return False, f'{", ".join(allowed_extensions)} 파일만 업로드 가능합니다.'
    
    return True, None

def allowed_file(filename, allowed_extensions):
    """파일 확장자 검사"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def secure_filename(filename):
    """안전한 파일명 생성"""
    import re
    # 한글과 영숫자, 점, 하이픈, 언더스코어만 허용
    filename = re.sub(r'[^\w가-힣\.\-_]', '', filename)
    return filename