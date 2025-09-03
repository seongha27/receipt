"""
네이버 플레이스 스크래퍼 모듈 - FastAPI용
"""
import requests
from bs4 import BeautifulSoup
import re
import json
import time
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

def get_chrome_driver():
    """Chrome WebDriver 설정"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        print(f"ChromeDriver 설정 실패: {e}")
        return None

def extract_place_id_from_url(url):
    """네이버 플레이스 URL에서 place_id 추출"""
    try:
        print(f"DEBUG: 입력된 URL: {url}")
        
        # 다양한 네이버 플레이스 URL 패턴 지원
        if 'naver.com' in url:
            # 패턴 1: https://place.naver.com/restaurant/1234567
            if '/restaurant/' in url:
                place_id = url.split('/restaurant/')[1].split('/')[0].split('?')[0]
                print(f"DEBUG: restaurant 패턴에서 추출: {place_id}")
                return place_id
            
            # 패턴 2: https://m.place.naver.com/restaurant/1234567
            if 'm.place.naver.com' in url and '/restaurant/' in url:
                place_id = url.split('/restaurant/')[1].split('/')[0].split('?')[0]
                print(f"DEBUG: m.place 패턴에서 추출: {place_id}")
                return place_id
                
            # 패턴 3: pcmap.place.naver.com
            if 'pcmap.place.naver.com' in url and '/restaurant/' in url:
                place_id = url.split('/restaurant/')[1].split('/')[0].split('?')[0]
                print(f"DEBUG: pcmap 패턴에서 추출: {place_id}")
                return place_id
            
            # 패턴 4: /place/ 경로
            if '/place/' in url:
                place_id = url.split('/place/')[1].split('/')[0].split('?')[0]
                print(f"DEBUG: place 패턴에서 추출: {place_id}")
                return place_id
            
            # 패턴 5: id 파라미터
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            if 'id' in query_params:
                place_id = query_params['id'][0]
                print(f"DEBUG: id 파라미터에서 추출: {place_id}")
                return place_id
        
        print(f"DEBUG: 어떤 패턴에도 매칭되지 않음")
        return None
    except Exception as e:
        print(f"URL 파싱 오류: {e}")
        return None

def get_naver_place_menu(place_url, timeout_seconds=30):
    """네이버 플레이스에서 메뉴 정보 추출"""
    # 임시로 테스트 데이터 반환 (실제 스크래핑 대신)
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
    
    # 실제 스크래핑 코드 (나중에 활성화)
    """
    driver = None
    try:
        place_id = extract_place_id_from_url(place_url)
        if not place_id:
            return {"success": False, "error": "유효하지 않은 네이버 플레이스 URL입니다."}
        
        driver = get_chrome_driver()
        if not driver:
            return {"success": False, "error": "ChromeDriver 설정에 실패했습니다."}
        
        # 네이버 플레이스 메뉴 페이지로 이동 (여러 URL 시도)
        menu_urls = [
            f"https://pcmap.place.naver.com/restaurant/{place_id}/menu",
            f"https://m.place.naver.com/restaurant/{place_id}/menu",
            f"https://place.naver.com/restaurant/{place_id}/menu"
        ]
        
        menu_url = menu_urls[0]  # 기본적으로 첫 번째 URL 사용
        print(f"메뉴 페이지 접속: {menu_url}")
        
        driver.get(menu_url)
        time.sleep(3)
        
        # 메뉴 정보 추출
        menus = []
        
        # 방법 1: 메뉴 리스트에서 추출
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".list_menu"))
            )
            
            menu_items = driver.find_elements(By.CSS_SELECTOR, ".list_menu .item_menu")
            
            for item in menu_items:
                try:
                    name_elem = item.find_element(By.CSS_SELECTOR, ".name")
                    price_elem = item.find_element(By.CSS_SELECTOR, ".price")
                    
                    name = name_elem.text.strip()
                    price_text = price_elem.text.strip()
                    
                    # 가격에서 숫자만 추출
                    price_numbers = re.findall(r'[\d,]+', price_text)
                    if price_numbers:
                        price = int(price_numbers[0].replace(',', ''))
                        menus.append({"name": name, "price": price})
                        
                except Exception as e:
                    continue
                    
        except TimeoutException:
            # 방법 2: 다른 셀렉터로 시도
            try:
                menu_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='menu']")
                for elem in menu_elements:
                    text = elem.text.strip()
                    if text and '원' in text:
                        lines = text.split('\n')
                        for line in lines:
                            if '원' in line and len(line.split()) >= 2:
                                parts = line.split()
                                name = parts[0]
                                price_text = parts[-1]
                                price_numbers = re.findall(r'[\d,]+', price_text)
                                if price_numbers:
                                    price = int(price_numbers[0].replace(',', ''))
                                    menus.append({"name": name, "price": price})
            except Exception as e:
                pass
        
        # 상호명 추출
        store_name = ""
        try:
            store_name_elem = driver.find_element(By.CSS_SELECTOR, ".GHAhO")
            store_name = store_name_elem.text.strip()
        except:
            try:
                store_name_elem = driver.find_element(By.CSS_SELECTOR, "h1")
                store_name = store_name_elem.text.strip()
            except:
                store_name = "추출된 상호명 없음"
        
        if menus:
            return {
                "success": True, 
                "store_name": store_name,
                "menus": menus,
                "total_count": len(menus)
            }
        else:
            return {
                "success": False, 
                "error": "메뉴 정보를 찾을 수 없습니다.",
                "store_name": store_name
            }
            
    except Exception as e:
        return {"success": False, "error": f"스크래핑 중 오류 발생: {str(e)}"}
    
    finally:
        if driver:
            driver.quit()

def format_menu_for_textarea(menu_data):
    """메뉴 데이터를 textarea용 텍스트로 포맷"""
    if not menu_data.get("success") or not menu_data.get("menus"):
        return ""
    
    lines = []
    for menu in menu_data["menus"]:
        lines.append(f"{menu['name']} {menu['price']:,}원")
    
    return "\n".join(lines)