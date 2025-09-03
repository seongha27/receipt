import os, random, re
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import piexif
from pathlib import Path
import io

font_path = str(Path(__file__).parent / "static" / "NanumGothic.ttf")

DEVICE_LIST = [
    ("samsung", "SM-N986N"), ("Apple", "iPhone 14 Pro"), ("LG", "LM-G900N"),
    ("Xiaomi", "Mi 11"), ("Google", "Pixel 7 Pro"), ("samsung", "Galaxy S25+"),
    ("Apple", "iPhone SE (3rd generation)"), ("samsung", "SM-G973N"),
    ("Apple", "iPhone 12"), ("Apple", "iPhone 13"),
]

CARD_PREFIXES = {
    "신한카드": "4500", "KB국민카드": "3560", "삼성카드": "4040",
    "롯데카드": "5383", "하나카드": "4882", "우리카드": "5248",
    "NH농협카드": "3568", "IBK기업카드": "4571", "씨티카드": "5409", "카카오뱅크": "5181"
}
KOREAN_CARD_COMPANIES = list(CARD_PREFIXES.items())

def ensure_font():
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"폰트 파일을 찾을 수 없습니다: {font_path}")

ensure_font()

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
            
        parts = line.split()
        if len(parts) >= 2:
            menu_name = ' '.join(parts[:-1])
            try:
                price_text = parts[-1]
                price = int(re.findall(r'\d+', price_text)[0])
                
                if apply_filter:
                    filtered_name = smart_filter_menu(menu_name)
                    if filtered_name:
                        menu_pool.append((filtered_name, price))
                else:
                    menu_pool.append((menu_name, price))
            except:
                continue
        else:
            if apply_filter:
                filtered_name = smart_filter_menu(line)
                if filtered_name:
                    menu_pool.append((filtered_name, random.randint(5000, 20000)))
            else:
                menu_pool.append((line, random.randint(5000, 20000)))
    
    if not menu_pool:
        menu_pool = [
            ("김치찌개", 8000),
            ("된장찌개", 7000),
            ("불고기", 15000),
            ("갈비탕", 12000),
            ("냉면", 9000),
            ("비빔밥", 8500),
            ("제육볶음", 10000),
            ("순대국", 8000)
        ]
    
    return menu_pool

def draw_centered(draw, text, font_obj, y_pos, width):
    bbox = draw.textbbox((0, 0), text, font=font_obj)
    w = bbox[2] - bbox[0]
    draw.text(((width - w) // 2, y_pos), text, font=font_obj, fill="black")
    return y_pos + bbox[3] - bbox[1] + 15

def draw_receipt(store_info, date, hour, minute, second, receipt_id, menu_pool):
    """영수증 이미지 생성 - 원본과 동일"""
    width, height = 600, 1800
    image = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, 26)
    bold_font = ImageFont.truetype(font_path, 30)
    y = 30
    
    y = draw_centered(draw, "[ 카드판매 영수증 ]", bold_font, y, width)
    y = draw_centered(draw, "(고객용)", font, y, width)
    
    for line in [
        f"사업자번호 : {store_info['사업자번호']}",
        store_info['상호명'],
        f"대표자 : {store_info['대표자명']}   TEL : {store_info['전화번호']}",
        store_info['주소'],
        f"판매시간: {date} {hour}:{minute}:{second}",
        f"영수번호: {receipt_id}"
    ]:
        draw.text((30, y), line, font=font, fill="black")
        y += 40
    
    draw.text((30, y), "=" * 60, font=font, fill="black"); y += 30
    draw.text((30, y), "상품명", font=font, fill="black")
    draw.text((250, y), "단가", font=font, fill="black")
    draw.text((350, y), "수량", font=font, fill="black")
    draw.text((450, y), "금액", font=font, fill="black"); y += 35
    draw.text((30, y), "=" * 60, font=font, fill="black"); y += 25

    selected_items = random.sample(menu_pool, k=random.randint(2, min(4, len(menu_pool))))
    total = 0
    for name, price in selected_items:
        qty = random.randint(1, 3)
        amount = price * qty
        total += amount
        draw.text((30, y), name, font=font, fill="black")
        draw.text((250, y), f"{price:,}", font=font, fill="black")
        draw.text((350, y), f"{qty}", font=font, fill="black")
        draw.text((450, y), f"{amount:,}", font=font, fill="black"); y += 35

    draw.text((30, y), "=" * 60, font=font, fill="black"); y += 45
    supply = int(total / 1.1)
    vat = total - supply
    for line in [
        f"합계 : {total:,}",
        f"공급가 : {supply:,}",
        f"부가세 : {vat:,}"
    ]:
        draw.text((30, y), line, font=font, fill="black"); y += 55
    
    y += 20
    card_company, prefix = random.choice(KOREAN_CARD_COMPANIES)
    card_no = f"{prefix}-****-****-{random.randint(1000, 9999)}"
    approval_num = random.randint(100000, 999999)
    full_datetime = f"{date} {hour}:{minute}:{second}"

    for line in [
        f"[카드종류] {card_company} [할부개월] 일시불",
        f"[카드번호] {card_no}",
        f"[승인일시] {full_datetime}",
        f"[승인번호] {approval_num}",
        f"[카드매출] {total:,}",
        f"- 공급가 : {supply:,}",
        f"- 부가세 : {vat:,}"
    ]:
        draw.text((30, y), line, font=font, fill="black"); y += 55

    return image

def generate_receipts_batch_web(store_info, menu_pool, start_date, end_date, daily_count, start_hour=11, end_hour=21):
    """웹용 영수증 배치 생성 - 원본 방식"""
    receipts = []
    
    current_date = start_date
    receipt_number = 1
    
    while current_date <= end_date:
        for i in range(daily_count):
            hour = random.randint(start_hour, end_hour)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            
            receipt_img = draw_receipt(
                store_info, 
                current_date.strftime('%Y-%m-%d'),
                f"{hour:02d}", f"{minute:02d}", f"{second:02d}",
                receipt_number,
                menu_pool
            )
            
            img_byte_arr = io.BytesIO()
            receipt_img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            date_str = current_date.strftime('%Y-%m-%d')
            receipt_path = f"{store_info['상호명']}/{date_str}/receipt_{receipt_number:03d}.jpg"
            
            receipts.append((img_byte_arr, receipt_path))
            receipt_number += 1
            
        current_date += timedelta(days=1)
    
    return receipts