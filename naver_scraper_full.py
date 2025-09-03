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
import subprocess
import os

def get_chrome_driver():
    """Chrome WebDriver 설정"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 백그라운드 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    
    try:
        # ChromeDriver 자동 설치 및 사용
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        
        # 최신 ChromeDriver 강제 다운로드
        service = ChromeService(ChromeDriverManager(driver_cache_valid_range=1).install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 자동화 감지 방지
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        print(f"ChromeDriver 설정 실패: {e}")
        
        # 백업: 시스템 ChromeDriver 사용 시도
        try:
            print("시스템 ChromeDriver 사용 시도...")
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e2:
            print(f"시스템 ChromeDriver도 실패: {e2}")
            return None

def get_naver_place_info(url):
    """네이버 플레이스에서 메뉴 정보 추출 - 실제 스크래핑"""
    if not url or 'naver.com' not in url:
        return []
    
    driver = None
    try:
        driver = get_chrome_driver()
        if not driver:
            return []
        
        print(f"페이지 로딩 중: {url}")
        driver.get(url)
        
        # 페이지 로딩 대기
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)
        
        # 메뉴 추출
        menu_items = []
        
        # 방법 1: span.lPzHi와 em 태그 직접 찾기
        try:
            menu_name_elements = driver.find_elements(By.CSS_SELECTOR, "span.lPzHi")
            print(f"메뉴명 요소 {len(menu_name_elements)}개 발견")
            
            for menu_name_elem in menu_name_elements:
                try:
                    menu_name = menu_name_elem.text.strip()
                    if not menu_name:
                        continue
                    
                    # em 태그에서 가격 찾기
                    parent = menu_name_elem.find_element(By.XPATH, "./../..")
                    em_elements = parent.find_elements(By.CSS_SELECTOR, "em")
                    
                    for em_elem in em_elements:
                        em_text = em_elem.text.strip()
                        price_numbers = re.findall(r'[\d,]+', em_text)
                        if price_numbers:
                            price = int(price_numbers[0].replace(',', ''))
                            if price > 1000:
                                menu_items.append((menu_name, price))
                                print(f"메뉴 추출: {menu_name} - {price}원")
                                break
                
                except:
                    continue
        
        except Exception as e:
            print(f"메뉴 추출 오류: {e}")
        
        # 방법 2: 페이지 소스에서 정규식으로 추출
        if not menu_items:
            page_source = driver.page_source
            patterns = [
                r'<span class="lPzHi">([^<]+)</span>.*?<em[^>]*>([^<]+)</em>',
                r'"name":"([^"]+)".*?"price":"?(\d+)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_source, re.DOTALL)
                for match in matches:
                    try:
                        name = match[0].strip()
                        price_text = match[1].strip()
                        price_numbers = re.findall(r'[\d,]+', price_text)
                        if price_numbers:
                            price = int(price_numbers[0].replace(',', ''))
                            if len(name) > 1 and price > 1000:
                                menu_items.append((name, price))
                    except:
                        continue
                
                if menu_items:
                    break
        
        # 중복 제거
        unique_items = []
        seen = set()
        for name, price in menu_items:
            if name not in seen:
                seen.add(name)
                unique_items.append((name, price))
        
        return unique_items[:20]
        
    except Exception as e:
        print(f"네이버 스크래핑 오류: {e}")
        return []
    
    finally:
        if driver:
            driver.quit()

def get_naver_place_menu(url):
    """네이버 플레이스에서 메뉴만 추출"""
    return get_naver_place_info(url)

def format_menu_for_textarea(menu_items, apply_filter=False):
    """메뉴 리스트를 textarea 형식으로 변환"""
    if apply_filter:
        filtered_items = []
        for name, price in menu_items:
            # 7글자 이하만 사용
            if len(name) <= 7:
                filtered_items.append((name, price))
            else:
                # 공백 제거해서 7글자 이하가 되면 사용
                no_space = name.replace(" ", "")
                if len(no_space) <= 7:
                    filtered_items.append((no_space, price))
        return '\n'.join([f"{name} {price}원" for name, price in filtered_items])
    else:
        return '\n'.join([f"{name} {price}원" for name, price in menu_items])