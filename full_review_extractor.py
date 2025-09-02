#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
정확히 수정된 full_review_extractor.py
기존 구글시트 방식과 동일하게 작동
- 업체명 찾기 → 해당 리뷰 박스에서만 날짜 추출
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
    기존 구글시트와 동일한 방식의 네이버 리뷰 추출
    1. 업체명 찾기
    2. 해당 리뷰 박스에서만 날짜/내용 추출  
    3. 접기 버튼으로 원상태 복구
    """
    driver = None
    try:
        # 셀레니움 드라이버 설정
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(5)
        
        logging.info(f"리뷰 추출 시작: {review_url} / 업체명: {expected_shop_name}")
        
        # 페이지 로드
        driver.get(review_url)
        
        # 리디렉션 대기 (naver.me 단축 URL인 경우)
        if "naver.me" in review_url:
            WebDriverWait(driver, 10).until(
                lambda d: d.current_url != review_url
            )
            logging.info(f"리디렉션 완료: {driver.current_url}")
        
        time.sleep(3)  # 페이지 로딩 대기
        
        # 업체명과 일치하는 리뷰 블록 찾기 (기존 구글시트 방식)
        target_review_block = find_review_block_by_shop_name(driver, expected_shop_name)
        
        if not target_review_block:
            logging.warning(f"업체명 '{expected_shop_name}'과 일치하는 리뷰를 찾지 못했습니다")
            return "일치하는 업체명의 리뷰를 찾을 수 없습니다", "영수증 날짜를 찾을 수 없습니다"
        
        logging.info(f"업체명 '{expected_shop_name}' 매칭 성공")
        
        # 해당 리뷰 블록의 더보기 버튼 클릭
        click_more_button_in_block(driver, target_review_block, expected_shop_name)
        
        # 페이지 다시 파싱 (더보기 클릭 후)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 업체명으로 리뷰 블록 다시 찾기 (더보기 클릭 후 DOM 변경됨)
        target_review_block = find_target_review_block_in_soup(soup, expected_shop_name)
        
        if not target_review_block:
            logging.error("더보기 클릭 후 리뷰 블록을 다시 찾을 수 없습니다")
            return "리뷰 블록 찾기 실패", "영수증 날짜를 찾을 수 없습니다"
        
        # 해당 리뷰 블록에서만 내용과 날짜 추출
        review_text = extract_review_text_from_block(target_review_block)
        receipt_date = extract_receipt_date_from_block(target_review_block)
        
        # 접기 버튼으로 원상태 복구
        click_collapse_buttons(driver)
        
        logging.info(f"추출 완료 - 업체: {expected_shop_name}, 날짜: {receipt_date}, 텍스트 길이: {len(review_text)}")
        
        return review_text, receipt_date
        
    except Exception as e:
        logging.error(f"리뷰 추출 중 오류: {str(e)}")
        return "오류 발생", "날짜 추출 실패"
        
    finally:
        if driver:
            try:
                click_collapse_buttons(driver)  # 최종 정리
            except:
                pass
            driver.quit()

def find_review_block_by_shop_name(driver, expected_shop_name):
    """업체명으로 리뷰 블록 찾기 (스크롤 포함)"""
    try:
        # 현재 페이지에서 먼저 찾기
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        review_blocks = soup.find_all('div', class_='hahVh2')
        
        for block in review_blocks:
            shop_elem = block.find('span', class_='pui__pv1E2a')
            if shop_elem and shop_elem.text.strip() == expected_shop_name:
                logging.info(f"업체명 '{expected_shop_name}' 찾음 (스크롤 없이)")
                return block
        
        # 못 찾았으면 스크롤하면서 찾기
        logging.info("스크롤하면서 업체명 검색 시작")
        for scroll_count in range(10):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            review_blocks = soup.find_all('div', class_='hahVh2')
            
            for block in review_blocks:
                shop_elem = block.find('span', class_='pui__pv1E2a')
                if shop_elem and shop_elem.text.strip() == expected_shop_name:
                    logging.info(f"업체명 '{expected_shop_name}' 찾음 (스크롤 {scroll_count+1}회)")
                    return block
        
        return None
        
    except Exception as e:
        logging.error(f"업체명 찾기 중 오류: {str(e)}")
        return None

def find_target_review_block_in_soup(soup, expected_shop_name):
    """BeautifulSoup에서 업체명으로 리뷰 블록 찾기"""
    try:
        review_blocks = soup.find_all('div', class_='hahVh2')
        for block in review_blocks:
            shop_elem = block.find('span', class_='pui__pv1E2a')
            if shop_elem and shop_elem.text.strip() == expected_shop_name:
                return block
        return None
    except Exception as e:
        logging.error(f"리뷰 블록 찾기 오류: {str(e)}")
        return None

def click_more_button_in_block(driver, target_block, expected_shop_name):
    """특정 리뷰 블록의 더보기 버튼 클릭"""
    try:
        # Selenium에서 업체명으로 리뷰 블록들 찾기
        review_blocks_selenium = driver.find_elements(By.CSS_SELECTOR, "div.hahVh2")
        
        for selenium_block in review_blocks_selenium:
            try:
                # 업체명 확인
                if expected_shop_name in selenium_block.text:
                    # 해당 블록의 더보기 버튼 찾기
                    more_selectors = [
                        "a[data-pui-click-code='otherreviewfeed.rvshowmore']",
                        "a[data-pui-click-code*='showmore']",
                        "span.TeItc"  # "펼쳐서 더보기"
                    ]
                    
                    for selector in more_selectors:
                        try:
                            more_btn = selenium_block.find_element(By.CSS_SELECTOR, selector)
                            if more_btn.is_displayed():
                                driver.execute_script("arguments[0].scrollIntoView(true);", more_btn)
                                time.sleep(0.5)
                                
                                # span인 경우 부모 요소 클릭
                                if more_btn.tag_name == 'span' and 'TeItc' in more_btn.get_attribute('class'):
                                    parent = more_btn.find_element(By.XPATH, "./..")
                                    driver.execute_script("arguments[0].click();", parent)
                                else:
                                    driver.execute_script("arguments[0].click();", more_btn)
                                
                                logging.info(f"해당 리뷰의 더보기 버튼 클릭 성공 ({selector})")
                                time.sleep(1)
                                return
                        except:
                            continue
                    
                    break
                    
            except Exception as e:
                continue
                
        logging.info("더보기 버튼을 찾을 수 없음 (이미 펼쳐진 상태일 수 있음)")
        
    except Exception as e:
        logging.warning(f"더보기 버튼 클릭 중 오류: {str(e)}")

def click_collapse_buttons(driver):
    """모든 접기 버튼 클릭"""
    try:
        clicked_count = 0
        
        # 접기 관련 텍스트들
        collapse_texts = [
            '접어두기', '간단히', '접기', '줄이기', '닫기', 
            '접어서', '접어 보기', '간단히 보기', '줄여서 보기'
        ]
        
        # 모든 클릭 가능한 요소들 찾기
        all_elements = driver.find_elements(By.CSS_SELECTOR, "span, button, a, div")
        
        for element in all_elements:
            try:
                if element.is_displayed() and element.text:
                    element_text = element.text.strip()
                    
                    # 접기 관련 텍스트가 포함되어 있는지 확인
                    if any(collapse_text in element_text for collapse_text in collapse_texts):
                        
                        if element.tag_name in ['button', 'a'] or element.get_attribute('onclick'):
                            driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(0.3)
                            driver.execute_script("arguments[0].click();", element)
                            clicked_count += 1
                            logging.info(f"접기 버튼 클릭: {element_text[:20]}...")
                            time.sleep(0.5)
                        else:
                            # span인 경우 부모 요소 클릭 시도
                            if element.tag_name == 'span':
                                try:
                                    parent = element.find_element(By.XPATH, "./..")
                                    if parent.is_displayed():
                                        driver.execute_script("arguments[0].scrollIntoView(true);", parent)
                                        time.sleep(0.3)
                                        driver.execute_script("arguments[0].click();", parent)
                                        clicked_count += 1
                                        logging.info(f"접기 부모 버튼 클릭: {element_text[:20]}...")
                                        time.sleep(0.5)
                                except:
                                    pass
                                    
            except Exception:
                continue
        
        if clicked_count > 0:
            logging.info(f"총 {clicked_count}개 접기 버튼 클릭 완료")
        else:
            logging.info("접기 버튼 없음 (정상 - 이미 접힌 상태)")
            
    except Exception as e:
        logging.warning(f"접기 버튼 클릭 중 오류: {str(e)}")

def extract_review_text_from_block(review_block):
    """특정 리뷰 블록에서 리뷰 텍스트 추출"""
    try:
        # 리뷰 본문 추출 (여러 방식 시도)
        selectors = [
            'div.pui__vn15t2',  # 기본 리뷰 텍스트
            'a[data-pui-click-code="reviewend.text"]',  # 링크 형태
            'div[class*="review"]',
            'div[class*="comment"]'
        ]
        
        for selector in selectors:
            review_elem = review_block.select_one(selector)
            if review_elem:
                review_text = review_elem.get_text(strip=True)
                if review_text and len(review_text) > 10:  # 최소 길이 확인
                    logging.info(f"리뷰 본문 추출 성공 ({selector}): {review_text[:50]}...")
                    return review_text
        
        # 모든 셀렉터가 실패했을 경우 전체 텍스트에서 정리해서 추출
        full_text = review_block.get_text(separator=' ', strip=True)
        
        # 불필요한 메타 정보 제거
        unwanted_patterns = [
            r'mmn\*{4}',  # 사용자명
            r'리뷰 \d+', r'사진 \d+',  # 메타 정보
            r'팔로우', r'반응 남기기',  # 버튼 텍스트
            r'\d+번째 방문', r'방문일', r'인증 수단', r'영수증',  # 라벨들
            r'\d+\.\d+\.[가-힣요일]+',  # 날짜들
            r'스타일 추천을 잘해줘요'  # 키워드들
        ]
        
        clean_text = full_text
        for pattern in unwanted_patterns:
            clean_text = re.sub(pattern, '', clean_text)
        
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if len(clean_text) > 10:
            logging.info(f"정리된 텍스트로 추출: {clean_text[:50]}...")
            return clean_text
            
        return "리뷰 본문을 찾을 수 없습니다"
        
    except Exception as e:
        logging.error(f"리뷰 텍스트 추출 중 오류: {str(e)}")
        return "리뷰 텍스트 추출 실패"

def extract_receipt_date_from_block(review_block):
    """특정 리뷰 블록에서만 영수증 날짜 추출 (핵심 수정 부분)"""
    try:
        logging.info("=== 리뷰 블록에서 날짜 추출 시작 ===")
        
        # 해당 리뷰 블록에서만 time 요소들 찾기
        time_elements = review_block.find_all('time')
        logging.info(f"해당 리뷰 블록에서 발견된 time 요소 개수: {len(time_elements)}")
        
        receipt_date = ""
        
        # 1차: 영수증 날짜 형식 (요일 포함) 우선 선택
        for i, time_elem in enumerate(time_elements):
            date_text = time_elem.get_text(strip=True)
            attrs = str(time_elem.attrs) if time_elem.attrs else "없음"
            logging.info(f"  Time 요소 {i+1}: '{date_text}' - 속성: {attrs}")
            
            # 영수증 날짜 형식 확인 (8.28.목 형태)
            if is_receipt_date_format(date_text):
                receipt_date = date_text
                logging.info(f"  ✅ 영수증 날짜로 선택: {receipt_date}")
                break
            else:
                logging.info(f"  ❌ 영수증 날짜 형식 아님: {date_text}")
        
        # 2차: 못 찾았으면 aria-hidden='true' 속성 시도
        if not receipt_date:
            time_elem = review_block.find('time', {'aria-hidden': 'true'})
            if time_elem:
                receipt_date = time_elem.get_text(strip=True)
                logging.info(f"  aria-hidden 방식으로 찾은 날짜: {receipt_date}")
        
        # 3차: 그래도 못 찾았으면 첫 번째 time 요소
        if not receipt_date and time_elements:
            receipt_date = time_elements[0].get_text(strip=True)
            logging.info(f"  첫 번째 time 요소 사용: {receipt_date}")
        
        result = receipt_date or "영수증 날짜를 찾을 수 없습니다"
        logging.info(f"=== 최종 선택된 날짜: {result} ===")
        
        return result
        
    except Exception as e:
        logging.error(f"영수증 날짜 추출 중 오류: {str(e)}")
        return "날짜 추출 실패"

def is_receipt_date_format(date_text):
    """영수증 날짜 형식인지 확인 (요일 포함 여부)"""
    if not date_text:
        return False
    
    # 영수증 날짜 패턴들 (요일 필수 포함)
    receipt_patterns = [
        r'\d{1,2}\.\d{1,2}\.[월화수목금토일]',  # 8.28.목
        r'\d{4}\.\d{1,2}\.\d{1,2}\.[월화수목금토일]',  # 2024.8.28.목
        r'\d{1,2}/\d{1,2}\([월화수목금토일]\)',  # 8/28(목)
        r'\d{4}/\d{1,2}/\d{1,2}\([월화수목금토일]\)',  # 2024/8/28(목)
    ]
    
    for pattern in receipt_patterns:
        if re.search(pattern, date_text):
            logging.debug(f"영수증 날짜 패턴 매치: '{date_text}' -> {pattern}")
            return True
    
    return False

# 테스트 함수
def test_with_sample_data():
    """샘플 데이터로 테스트"""
    print("=== 수정된 리뷰 추출기 테스트 ===")
    
    # 실제 테스트 시 이 값들을 실제 데이터로 변경
    test_url = "https://naver.me/sample"  
    test_shop_name = "테스트업체"
    
    review_text, receipt_date = extract_naver_review_full(test_url, test_shop_name)
    
    print(f"추출 결과:")
    print(f"  영수증 날짜: {receipt_date}")
    print(f"  리뷰 텍스트: {review_text[:100]}...")
    
    # 결과 검증
    if "8.28.목" in receipt_date or "8.27.수" in receipt_date:
        print("✅ 요일 포함 날짜 추출 성공!")
    elif any(day in receipt_date for day in '월화수목금토일'):
        print("✅ 영수증 날짜 형식 확인됨")
    else:
        print("❌ 날짜 형식 확인 필요")

if __name__ == "__main__":
    test_with_sample_data()
    
