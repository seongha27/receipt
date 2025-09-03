"""
영수증 생성기 모듈 - FastAPI용
"""
import os
import random
import io
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import piexif
from pathlib import Path
import tempfile
import zipfile

# 폰트 경로 설정 (원본과 동일)
font_path = str(Path(__file__).parent / "static" / "NanumGothic.ttf")

# 기기 목록
DEVICE_LIST = [
    ("samsung", "SM-N986N"), ("Apple", "iPhone 14 Pro"), ("LG", "LM-G900N"),
    ("Xiaomi", "Mi 11"), ("Google", "Pixel 7 Pro"), ("samsung", "Galaxy S25+"),
    ("Apple", "iPhone SE (3rd generation)"), ("samsung", "SM-G973N"),
    ("Apple", "iPhone 12"), ("Apple", "iPhone 13"),
]

# 카드 회사 정보
CARD_PREFIXES = {
    "신한카드": "4500", "KB국민카드": "3560", "삼성카드": "4040",
    "롯데카드": "5383", "하나카드": "4882", "우리카드": "5248",
    "NH농협카드": "3568", "IBK기업카드": "4571", "씨티카드": "5409", "카카오뱅크": "5181"
}

def ensure_font():
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"폰트 파일을 찾을 수 없습니다: {font_path}")

ensure_font()

# safe_text_draw 제거 - 원본과 동일하게 단순한 draw.text 사용

def smart_filter_menu(menu_name, max_length=7):
    """메뉴명을 7글자 이하로 필터링"""
    if len(menu_name) <= max_length:
        return menu_name
    
    no_space = menu_name.replace(" ", "").replace("　", "")
    if len(no_space) <= max_length:
        return no_space
    
    return None

def parse_menu_input(menu_text, apply_filter=False):
    """메뉴 텍스트를 파싱하여 메뉴 리스트 반환"""
    menu_pool = []
    lines = menu_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 가격 패턴 찾기
        if '원' in line or ',' in line:
            parts = line.split()
            if len(parts) >= 2:
                menu_name = parts[0]
                price_str = parts[-1].replace(',', '').replace('원', '')
                try:
                    price = int(price_str)
                    if apply_filter:
                        filtered_name = smart_filter_menu(menu_name)
                        if filtered_name:
                            menu_pool.append((filtered_name, price))
                    else:
                        menu_pool.append((menu_name, price))
                except ValueError:
                    continue
    
    return menu_pool

def generate_random_receipt_number():
    """랜덤 영수증 번호 생성"""
    return f"{random.randint(1000, 9999)}-{random.randint(100000, 999999)}"

def generate_random_card_info():
    """랜덤 카드 정보 생성"""
    card_company, prefix = random.choice(list(CARD_PREFIXES.items()))
    card_number = f"{prefix}-{random.randint(1000, 9999)}-****-{random.randint(1000, 9999)}"
    return card_company, card_number

def create_receipt_image(store_name, menu_items, total_amount, receipt_date=None):
    """영수증 이미지 생성"""
    if receipt_date is None:
        receipt_date = datetime.now()
    
    # 이미지 크기 설정
    width, height = 400, 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # 폰트 설정
    try:
        if ensure_font():
            font_large = ImageFont.truetype(font_path, 20)
            font_medium = ImageFont.truetype(font_path, 16)
            font_small = ImageFont.truetype(font_path, 14)
        else:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # 영수증 내용 그리기
    y_pos = 20
    
    # 상호명
    draw.text((width//2, y_pos), store_name, font_large, anchor="mt")
    y_pos += 40
    
    # 구분선
    draw.line([(20, y_pos), (width-20, y_pos)], fill='black', width=1)
    y_pos += 20
    
    # 메뉴 항목들
    for menu_name, price in menu_items:
        draw.text((30, y_pos), menu_name, font_medium)
        draw.text((width-30, y_pos), f"{price:,}원", font_medium, anchor="rt")
        y_pos += 25
    
    # 구분선
    y_pos += 10
    draw.line([(20, y_pos), (width-20, y_pos)], fill='black', width=1)
    y_pos += 20
    
    # 총액
    draw.text((30, y_pos), "합계", font_large)
    draw.text((width-30, y_pos), f"{total_amount:,}원", font_large, anchor="rt")
    y_pos += 40
    
    # 결제 정보
    card_company, card_number = generate_random_card_info()
    draw.text((30, y_pos), f"카드: {card_company}", font_small)
    y_pos += 20
    draw.text((30, y_pos), f"번호: {card_number}", font_small)
    y_pos += 20
    
    # 날짜/시간
    draw.text((30, y_pos), f"일시: {receipt_date.strftime('%Y-%m-%d %H:%M:%S')}", font_small)
    y_pos += 20
    
    # 영수증 번호
    receipt_num = generate_random_receipt_number()
    draw.text((30, y_pos), f"영수증번호: {receipt_num}", font_small)
    
    return img

def remove_image_metadata(image):
    """이미지 메타데이터 제거"""
    try:
        # EXIF 데이터 제거
        img_no_exif = Image.new(image.mode, image.size)
        img_no_exif.putdata(list(image.getdata()))
        return img_no_exif
    except:
        return image

def generate_receipts_batch_web(store_info, menu_pool, start_date, end_date, daily_count, start_hour=11, end_hour=21):
    """웹용 영수증 배치 생성 - 고급 버전"""
    receipts = []
    
    current_date = start_date
    receipt_number = 1
    
    while current_date <= end_date:
        for i in range(daily_count):
            # 랜덤 시간 생성 (영업 시간 내)
            hour = random.randint(start_hour, end_hour)
            minute = random.randint(0, 59)
            receipt_datetime = current_date.replace(hour=hour, minute=minute)
            
            # 랜덤 메뉴 선택 (1-5개)
            selected_menus = random.sample(menu_pool, min(random.randint(1, 5), len(menu_pool)))
            
            # 총액 계산
            total_amount = sum(price for _, price in selected_menus)
            
            # 영수증 이미지 생성 (업체 정보 포함)
            receipt_img = create_receipt_image_full(
                store_info['상호명'], store_info['사업자번호'], store_info['대표자명'], 
                store_info['전화번호'], store_info['주소'], 
                selected_menus, total_amount, receipt_datetime
            )
            
            # 메타데이터 제거
            receipt_img = remove_image_metadata(receipt_img)
            
            # 이미지를 바이트로 변환
            img_byte_arr = io.BytesIO()
            receipt_img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            # 파일 경로 생성
            date_str = current_date.strftime('%Y-%m-%d')
            receipt_path = f"{store_info['상호명']}/{date_str}/receipt_{receipt_number:03d}.jpg"
            
            receipts.append((img_byte_arr, receipt_path))
            receipt_number += 1
            
        # 다음 날로 이동
        current_date += timedelta(days=1)
    
    return receipts

def create_receipt_image_full(store_name, biz_num, owner_name, phone, address, menu_items, total_amount, receipt_date):
    """완전한 업체 정보가 포함된 영수증 이미지 생성 - 원본 방식"""
    width, height = 600, 1800  # 원본과 동일한 크기
    image = Image.new("RGB", (width, height), (245, 245, 245))  # 원본과 동일한 배경색
    draw = ImageDraw.Draw(image)
    
    # 폰트 설정 (원본과 동일)
    font = ImageFont.truetype(font_path, 26)
    bold_font = ImageFont.truetype(font_path, 30)
    
    y = 30
    
    # 헤더 (원본과 동일)
    def draw_centered(draw, text, font_obj, y_pos, width):
        bbox = draw.textbbox((0, 0), text, font=font_obj)
        w = bbox[2] - bbox[0]
        draw.text(((width - w) // 2, y_pos), text, font=font_obj, fill="black")
        return y_pos + bbox[3] - bbox[1] + 15
    
    y = draw_centered(draw, "[ 카드판매 영수증 ]", bold_font, y, width)
    y = draw_centered(draw, "(고객용)", font, y, width)
    
    # 업체 정보 (원본과 동일)
    for line in [
        f"사업자번호 : {biz_num}",
        store_name,
        f"대표자 : {owner_name}   TEL : {phone}",
        address,
        f"판매시간: {receipt_date.strftime('%Y-%m-%d %H:%M:%S')}",
        f"영수번호: {generate_receipt_number()}"
    ]:
        draw.text((30, y), line, font=font, fill="black")
        y += 40
    
    # 구분선
    y_pos += 20
    draw.line([(30, y_pos), (width-30, y_pos)], fill='black', width=2)
    y_pos += 30
    
    # 메뉴 항목들
    for menu_name, price in menu_items:
        draw.text((40, y_pos), menu_name, font_medium)
        draw.text((width-40, y_pos), f"{price:,}원", font_medium, anchor="rt")
        y_pos += 30
    
    # 구분선
    y_pos += 20
    draw.line([(30, y_pos), (width-30, y_pos)], fill='black', width=2)
    y_pos += 30
    
    # 총액 (강조)
    draw.text((40, y_pos), "합계", font_large)
    draw.text((width-40, y_pos), f"{total_amount:,}원", font_large, anchor="rt")
    y_pos += 50
    
    # 결제 정보
    card_company, card_number = generate_random_card_info()
    draw.text((40, y_pos), f"결제: {card_company}", font_small)
    y_pos += 25
    draw.text((40, y_pos), f"카드번호: {card_number}", font_small)
    y_pos += 25
    
    # 날짜/시간
    draw.text((40, y_pos), f"결제일시: {receipt_date.strftime('%Y-%m-%d %H:%M:%S')}", font_small)
    y_pos += 25
    
    # 영수증 번호
    receipt_num = generate_random_receipt_number()
    draw.text((40, y_pos), f"영수증번호: {receipt_num}", font_small)
    
    return remove_image_metadata(img)

def create_receipts_zip(receipts):
    """영수증들을 ZIP 파일로 생성"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for receipt in receipts:
            zip_file.writestr(receipt['filename'], receipt['image_data'])
    
    zip_buffer.seek(0)
    return zip_buffer