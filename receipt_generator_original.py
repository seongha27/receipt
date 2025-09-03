import os, random
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
    # 1. 이미 7글자 이하면 그대로 사용
    if len(menu_name) <= max_length:
        return menu_name
    
    # 2. 공백 제거해서 7글자 이하가 되면 공백 제거
    no_space = menu_name.replace(" ", "").replace("　", "")  # 일반 공백과 전각 공백 모두 제거
    if len(no_space) <= max_length:
        return no_space
    
    # 3. 그래도 길면 None 반환 (제외)
    return None

def parse_menu_input(menu_text, apply_filter=False):
    """메뉴 텍스트를 파싱하여 메뉴 리스트 반환"""
    menu_pool = []
    lines = menu_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 메뉴명과 가격 분리 시도
        parts = line.split()
        if len(parts) >= 2:
            # 마지막 부분이 가격인지 확인
            menu_name = ' '.join(parts[:-1])
            try:
                price_text = parts[-1]
                # 숫자만 추출
                import re
                price_numbers = re.findall(r'\d+', price_text)
                if price_numbers:
                    price = int(price_numbers[0])
                    
                    if apply_filter:
                        filtered_name = smart_filter_menu(menu_name)
                        if filtered_name:
                            menu_pool.append((filtered_name, price))
                    else:
                        menu_pool.append((menu_name, price))
                else:
                    raise ValueError("가격 정보 없음")
            except:
                # 가격 파싱 실패시 기본값 사용
                if apply_filter:
                    filtered_name = smart_filter_menu(line)
                    if filtered_name:
                        menu_pool.append((filtered_name, random.randint(5000, 20000)))
                else:
                    menu_pool.append((line, random.randint(5000, 20000)))
        else:
            # 가격 파싱 실패시 기본값 사용
            if apply_filter:
                filtered_name = smart_filter_menu(line)
                if filtered_name:
                    menu_pool.append((filtered_name, random.randint(5000, 20000)))
            else:
                menu_pool.append((line, random.randint(5000, 20000)))
    
    # 기본 메뉴가 없으면 샘플 메뉴 추가
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

def generate_spaced_times(start_hour, end_hour, count, min_gap_minutes=50):
    """최소 간격을 보장하는 시간들을 생성"""
    # 영업시간의 총 분 계산
    total_minutes = (end_hour - start_hour) * 60
    
    # 필요한 최소 시간 계산 (마지막 영수증 제외하고 간격 적용)
    min_required_minutes = (count - 1) * min_gap_minutes
    
    if min_required_minutes >= total_minutes:
        # 간격을 줄여서 맞춤
        actual_gap = max(1, total_minutes // count)
        print(f"[WARNING] 최소 간격 {min_gap_minutes}분을 {actual_gap}분으로 조정합니다.")
    else:
        actual_gap = min_gap_minutes
    
    times = []
    available_minutes = total_minutes - min_required_minutes
    
    for i in range(count):
        if i == 0:
            # 첫 번째 영수증은 영업시간 시작부터 가능한 범위에서 랜덤
            base_minutes = random.randint(0, available_minutes // count if available_minutes > 0 else 0)
        else:
            # 이전 시간에서 최소 간격 + 추가 랜덤 시간
            prev_time = times[i-1]
            prev_total_minutes = prev_time[0] * 60 + prev_time[1]
            
            extra_minutes = random.randint(0, min(30, (available_minutes // (count - i)) if count > i else 30))
            base_minutes = prev_total_minutes + actual_gap + extra_minutes - start_hour * 60
        
        # 영업시간을 넘지 않도록 조정
        base_minutes = min(base_minutes, total_minutes - 1)
        
        hour = start_hour + (base_minutes // 60)
        minute = base_minutes % 60
        second = random.randint(0, 59)
        
        times.append((hour, minute, second))
    
    return times

def draw_centered(draw, text, font_obj, y_pos, width):
    bbox = draw.textbbox((0, 0), text, font=font_obj)
    w = bbox[2] - bbox[0]
    draw.text(((width - w) // 2, y_pos), text, font=font_obj, fill="black")
    return y_pos + bbox[3] - bbox[1] + 15

def draw_receipt(store_info, date, hour, minute, second, receipt_id, menu_pool):
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

    selected_items = []
    total = 0
    while total < 20000:
        selected_items = random.sample(menu_pool, k=random.randint(2, min(4, len(menu_pool))))
        total = sum(price * random.randint(1, 3) for name, price in selected_items)

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

    y += 30
    y = draw_centered(draw, "신용카드 전표", font, y, width)
    y = draw_centered(draw, date.replace("-", "") + f"{hour}{minute}{second}" + str(receipt_id).zfill(6), font, y, width)

    device = random.choice(DEVICE_LIST)
    exif_dict = piexif.load(image.info.get("exif", piexif.dump({})))
    exif_dict["0th"][piexif.ImageIFD.Make] = device[0].encode()
    exif_dict["0th"][piexif.ImageIFD.Model] = device[1].encode()
    exif_bytes = piexif.dump(exif_dict)
    image.info["exif"] = exif_bytes

    return image

def generate_receipts_batch_web(store_info, menu_pool, start_date, end_date, daily_count, start_hour, end_hour):
    """
    지정한 날짜 범위와 개수, 영업시간 내에서 최소 50분 간격으로 생성.
    zip 내부에 상호명/날짜/파일이름.jpg 구조로 저장.
    """
    results = []
    receipt_id = random.randint(100000, 999999)
    store_name = store_info['상호명']
    
    for n in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=n)
        date_str = day.strftime("%Y-%m-%d")
        
        # 해당 날짜의 모든 영수증에 대한 시간을 미리 생성 (최소 50분 간격)
        daily_times = generate_spaced_times(start_hour, end_hour, daily_count, min_gap_minutes=50)
        
        for i in range(daily_count):
            hour, minute, second = daily_times[i]
            img = draw_receipt(
                store_info, date_str,
                f"{int(hour):02d}", f"{int(minute):02d}", f"{int(second):02d}",
                receipt_id, menu_pool
            )
            img_io = io.BytesIO()
            img.save(img_io, format="JPEG", exif=img.info["exif"])
            img_io.seek(0)
            # zip 내부 경로를 '상호명/날짜/파일이름.jpg'로 설정
            fname = f"{store_name}/{date_str}/{store_name}_{date_str}_{int(hour):02d}{int(minute):02d}{int(second):02d}_{receipt_id}.jpg"
            results.append((img_io, fname))
            receipt_id += 1
    return results