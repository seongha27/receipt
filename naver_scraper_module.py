"""
네이버 플레이스 스크래퍼 모듈 - FastAPI용 (간소화 버전)
"""

def extract_place_id_from_url(url):
    """네이버 플레이스 URL에서 place_id 추출"""
    try:
        print(f"DEBUG: 입력된 URL: {url}")
        
        if 'naver.com' in url:
            if '/restaurant/' in url:
                place_id = url.split('/restaurant/')[1].split('/')[0].split('?')[0]
                print(f"DEBUG: restaurant 패턴에서 추출: {place_id}")
                return place_id
        
        print(f"DEBUG: 어떤 패턴에도 매칭되지 않음")
        return None
    except Exception as e:
        print(f"URL 파싱 오류: {e}")
        return None

def get_naver_place_menu(place_url, timeout_seconds=30):
    """네이버 플레이스에서 메뉴 정보 추출"""
    place_id = extract_place_id_from_url(place_url)
    if not place_id:
        return {"success": False, "error": "유효하지 않은 네이버 플레이스 URL입니다."}
    
    # 테스트용 메뉴 데이터
    test_menus = [
        {"name": "김치찌개", "price": 8000},
        {"name": "된장찌개", "price": 7000},
        {"name": "불고기정식", "price": 15000},
        {"name": "비빔밥", "price": 9000},
        {"name": "냉면", "price": 8000},
        {"name": "갈비탕", "price": 12000},
        {"name": "삼겹살", "price": 18000}
    ]
    
    return {
        "success": True,
        "store_name": "테스트 음식점",
        "menus": test_menus,
        "total_count": len(test_menus)
    }

def format_menu_for_textarea(menu_data):
    """메뉴 데이터를 textarea용 텍스트로 포맷"""
    if not menu_data.get("success") or not menu_data.get("menus"):
        return ""
    
    lines = []
    for menu in menu_data["menus"]:
        lines.append(f"{menu['name']} {menu['price']:,}원")
    
    return "\n".join(lines)