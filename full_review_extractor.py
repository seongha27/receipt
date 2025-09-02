#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
수정된 full_review_extractor.py
- 정확한 영수증 날짜 추출 (8.28.목 vs 8.27.수 구분)
- 접기 버튼 기능 추가
"""

import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def extract_naver_review_full(review_url, expected_shop_name):
    """
    개선된 네이버 리뷰 추출 함수
    - 정확한 영수증 날짜 추출
    - 접기 버튼 기능
    """
    driver = None
    try:
        # 셀레니움 드라이버 설정
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless')  # 서버 환경에서는 headless 모드
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(5)
        
        logging.info(f"리뷰 추출 시작: {review_url}")
        
        # 페이지 로드
        driver.get(review_url)
        
        # 리디렉션 대기 (naver.me 단축 URL인 경우)
        if "naver.me" in review_url:
            WebDriverWait(driver, 10).until(
                lambda d: d.current_url != review_url
            )
            logging.info(f"리디렉션 완료: {driver.current_url}")
        
        time.sleep(3)  # 페이지 로딩 대기
        
        # 더보기 버튼 클릭 (있다면)
        click_more_buttons(driver)
        
        # HTML 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 리뷰 텍스트 추출
        review_text = extract_review_text(soup, expected_shop_name)
        
        # 개선된 영수증 날짜 추출
        receipt_date = extract_accurate_receipt_date(soup)
        
        # 접기 버튼 클릭 (페이지 상태 복구)
        click_collapse_buttons(driver)
        
        logging.info(f"추출 완료 - 날짜: {receipt_date}, 텍스트 길이: {len(review_text)}")
        
        return review_text, receipt_date
        
    except Exception as e:
        logging.error(f"리뷰 추출 중 오류: {str(e)}")
        return "오류 발생", "날짜 추출 실패"
        
    finally:
        if driver:
            driver.quit()

def click_more_buttons(driver):
    """더보기 버튼들 클릭"""
    try:
        clicked_count = 0
        
        # 1순위: "펼쳐서 더보기" span 요소
        try:
            more_spans = driver.find_elements(By.CSS_SELECTOR, 'span.TeItc')
            for span in more_spans:
                if span.is_displayed() and '펼쳐서 더보기' in span.text:
                    driver.execute_script("arguments[0].scrollIntoView(true);", span)
                    time.sleep(0.3)
                    # 부모 요소 클릭
                    parent = span.find_element(By.XPATH, "./..")
                    driver.execute_script("arguments[0].click();", parent)
                    clicked_count += 1
                    logging.info("펼쳐서 더보기 버튼 클릭 성공")
                    time.sleep(1)
        except Exception as e:
            logging.debug(f"TeItc 클래스 더보기 버튼 처리 중 오류: {str(e)}")
        
        # 2순위: data-pui-click-code 속성
        try:
            pui_buttons = driver.find_elements(By.CSS_SELECTOR, 'a[data-pui-click-code*="showmore"]')
            for button in pui_buttons:
                if button.is_displayed() and button.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", button)
                    clicked_count += 1
                    logging.info("data-pui 더보기 버튼 클릭 성공")
                    time.sleep(1)
        except Exception as e:
            logging.debug(f"data-pui 더보기 버튼 처리 중 오류: {str(e)}")
        
        # 3순위: 텍스트 기반 더보기 버튼
        try:
            all_elements = driver.find_elements(By.CSS_SELECTOR, "span, button, a")
            for element in all_elements:
                if (element.is_displayed() and element.text and 
                    ('더보기' in element.text or '펼쳐' in element.text)):
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(0.3)
                        driver.execute_script("arguments[0].click();", element)
                        clicked_count += 1
                        logging.info(f"텍스트 기반 더보기 클릭: {element.text[:20]}...")
                        time.sleep(1)
                        break
                    except:
                        continue
        except Exception as e:
            logging.debug(f"텍스트 기반 더보기 버튼 처리 중 오류: {str(e)}")
        
        if clicked_count > 0:
            logging.info(f"총 {clicked_count}개 더보기 버튼 클릭 완료")
        
    except Exception as e:
        logging.warning(f"더보기 버튼 클릭 중 오류: {str(e)}")

def click_collapse_buttons(driver):
    """접기 버튼들 클릭 (페이지 상태 복구)"""
    try:
        clicked_count = 0
        
        # 접기 관련 텍스트를 가진 요소들 찾기
        all_elements = driver.find_elements(By.CSS_SELECTOR, "span, button, a, div")
        
        for element in all_elements:
            try:
                if (element.is_displayed() and element.text and 
                    ('접어두기' in element.text or '간단히' in element.text or 
                     '접기' in element.text or '줄이기' in element.text or 
                     '닫기' in element.text or '접어서' in element.text or
                     '접어 보기' in element.text)):
                    
                    if element.tag_name in ['button', 'a'] or element.get_attribute('onclick'):
                        driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(0.3)
                        driver.execute_script("arguments[0].click();", element)
                        clicked_count += 1
                        logging.info(f"접기 버튼 클릭: {element.text[:20]}...")
                        time.sleep(0.5)
                    else:
                        # span이면 부모 요소 클릭 시도
                        if element.tag_name == 'span':
                            try:
                                parent = element.find_element(By.XPATH, "./..")
                                if parent.is_displayed():
                                    driver.execute_script("arguments[0].scrollIntoView(true);", parent)
                                    time.sleep(0.3)
                                    driver.execute_script("arguments[0].click();", parent)
                                    clicked_count += 1
                                    logging.info(f"접기 부모 버튼 클릭: {element.text[:20]}...")
                                    time.sleep(0.5)
                            except:
                                pass
                                
            except Exception:
                continue
        
        if clicked_count > 0:
            logging.info(f"총 {clicked_count}개 접기 버튼 클릭 완료")
        else:
            logging.info("접기 버튼을 찾을 수 없습니다 (정상 - 이미 접힌 상태일 수 있음)")
            
    except Exception as e:
        logging.warning(f"접기 버튼 클릭 중 오류: {str(e)}")

def extract_accurate_receipt_date(soup):
    """
    정확한 영수증 날짜 추출
    여러 time 요소 중 영수증 날짜 형식을 우선 선택
    """
    receipt_date = ""
    
    # 1차: 모든 time 요소에서 영수증 날짜 형식 찾기
    time_elements = soup.find_all('time')
    logging.info(f"페이지에서 발견된 time 요소 개수: {len(time_elements)}")
    
    for i, time_elem in enumerate(time_elements):
        date_text = time_elem.get_text(strip=True)
        attrs = str(time_elem.attrs) if time_elem.attrs else "없음"
        logging.info(f"Time 요소 {i+1}: '{date_text}' - 속성: {attrs}")
        
        # 영수증 날짜 형식 확인 (예: "8.28.목", "2024.8.28.목")
        if is_receipt_date_format(date_text):
            receipt_date = date_text
            logging.info(f"✅ 영수증 날짜로 선택: {receipt_date}")
            break
    
    # 2차: 못 찾았으면 기존 방식으로 재시도 (aria-hidden='true')
    if not receipt_date:
        time_elem = soup.find('time', {'aria-hidden': 'true'})
        if time_elem:
            receipt_date = time_elem.get_text(strip=True)
            logging.info(f"기본 방식으로 찾은 날짜: {receipt_date}")
    
    # 3차: 페이지 전체에서 날짜 패턴 검색 (최후의 수단)
    if not receipt_date:
        receipt_date = extract_date_from_page_text(soup.get_text())
        if receipt_date:
            logging.info(f"페이지 텍스트에서 찾은 날짜: {receipt_date}")
    
    result = receipt_date or "영수증 날짜를 찾을 수 없습니다"
    logging.info(f"최종 선택된 영수증 날짜: {result}")
    
    return result

def is_receipt_date_format(date_text):
    """영수증 날짜 형식인지 확인"""
    if not date_text:
        return False
    
    # 영수증 날짜 패턴들 (요일 포함)
    receipt_patterns = [
        r'\d{1,2}\.\d{1,2}\.[월화수목금토일]',  # 8.28.목
        r'\d{4}\.\d{1,2}\.\d{1,2}\.[월화수목금토일]',  # 2024.8.28.목
        r'\d{1,2}/\d{1,2}\([월화수목금토일]\)',  # 8/28(목)
        r'\d{4}/\d{1,2}/\d{1,2}\([월화수목금토일]\)',  # 2024/8/28(목)
    ]
    
    for pattern in receipt_patterns:
        if re.search(pattern, date_text):
            logging.debug(f"날짜 패턴 매치: '{date_text}' -> {pattern}")
            return True
    
    return False

def extract_date_from_page_text(text):
    """페이지 전체 텍스트에서 날짜 패턴 추출"""
    if not text:
        return ""
    
    patterns = [
        r'\d{1,2}\.\d{1,2}\.[월화수목금토일]',
        r'\d{4}\.\d{1,2}\.\d{1,2}\.[월화수목금토일]',
        r'\d{1,2}/\d{1,2}\([월화수목금토일]\)',
        r'\d{4}/\d{1,2}/\d{1,2}\([월화수목금토일]\)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            logging.debug(f"페이지 텍스트에서 날짜 발견: {match.group()}")
            return match.group()
    
    return ""

def extract_review_text(soup, expected_shop_name):
    """리뷰 텍스트 추출"""
    review_text = ""
    
    # 다양한 셀렉터로 리뷰 텍스트 시도
    selectors = [
        'a[data-pui-click-code="reviewend.text"]',
        'div.pui__vn15t2',
        'div[class*="review_text"]',
        'div[class*="comment"]'
    ]
    
    for selector in selectors:
        review_elem = soup.select_one(selector)
        if review_elem:
            review_text = review_elem.get_text(strip=True)
            logging.info(f"리뷰 본문 찾음 ({selector}): {review_text[:50]}...")
            break
    
    # 업체명으로 특정 리뷰 블록 찾기 (기존 로직)
    if not review_text and expected_shop_name:
        review_blocks = soup.find_all('div', class_='hahVh2')
        for block in review_blocks:
            shop_elem = block.find('span', class_='pui__pv1E2a')
            if shop_elem and shop_elem.text.strip() == expected_shop_name:
                review_div = block.find('div', class_='pui__vn15t2')
                if review_div:
                    review_text = review_div.text.strip()
                    logging.info(f"업체명 매칭으로 리뷰 찾음: {review_text[:50]}...")
                    break
    
    result = review_text or "리뷰 본문을 찾을 수 없습니다"
    return result

# 테스트 함수
def test_extract_function():
    """수정된 함수 테스트"""
    # 테스트 URL (실제 사용시 변경)
    test_url = "https://naver.me/sample"  # 실제 URL로 변경
    test_shop_name = "테스트업체"  # 실제 업체명으로 변경
    
    print("=== 수정된 리뷰 추출 함수 테스트 ===")
    review_text, receipt_date = extract_naver_review_full(test_url, test_shop_name)
    
    print(f"추출 결과:")
    print(f"  영수증 날짜: {receipt_date}")
    print(f"  리뷰 텍스트: {review_text[:100]}...")
    
    # 날짜 형식 검증
    if is_receipt_date_format(receipt_date):
        print("✅ 영수증 날짜 형식 검증 통과")
    else:
        print("❌ 영수증 날짜 형식 검증 실패")

if __name__ == "__main__":
    # 테스트 실행
    test_extract_function()
