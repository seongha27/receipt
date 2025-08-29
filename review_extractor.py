from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging
import time
from typing import Tuple, Optional
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NaverReviewExtractor:
    def __init__(self):
        self.driver = None
        
    def setup_selenium(self):
        """셀레니움 크롬 드라이버 설정"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--headless')  # 서버 배포시 필요
            options.add_argument('--remote-debugging-port=9222')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Railway/Render 등에서 Chrome 바이너리 경로 설정
            chrome_binary = os.getenv('GOOGLE_CHROME_BIN')
            if chrome_binary:
                options.binary_location = chrome_binary
            
            # ChromeDriver 경로 설정
            chrome_driver_path = os.getenv('CHROMEDRIVER_PATH')
            if chrome_driver_path:
                self.driver = webdriver.Chrome(executable_path=chrome_driver_path, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
                
            self.driver.implicitly_wait(5)
            
            logger.info("셀레니움 드라이버 설정 완료")
            return True
        except Exception as e:
            logger.error(f"셀레니움 드라이버 설정 실패: {str(e)}")
            logger.warning("Chrome이 설치되지 않은 환경에서는 리뷰 추출 기능을 사용할 수 없습니다")
            return False

    def extract_direct_review(self, url: str) -> Tuple[str, str]:
        """
        개별 리뷰 페이지에서 직접 추출 (새로운 링크 형식용)
        https://m.place.naver.com/my/review/... 형식
        """
        try:
            if not self.driver:
                if not self.setup_selenium():
                    return "드라이버 설정 실패", "드라이버 설정 실패"
                    
            self.driver.get(url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 리뷰 본문 추출 - data-pui-click-code="reviewend.text" 속성 사용
            review_text = ""
            review_elem = soup.find('a', {'data-pui-click-code': 'reviewend.text'})
            if review_elem:
                review_text = review_elem.get_text(strip=True)
                logger.info(f"리뷰 본문 찾음: {review_text[:50]}...")
            
            # 영수증 날짜 추출 - time 태그 사용
            receipt_date = ""
            time_elem = soup.find('time', {'aria-hidden': 'true'})
            if time_elem:
                receipt_date = time_elem.get_text(strip=True)
                logger.info(f"영수증 날짜 찾음: {receipt_date}")
            
            return review_text or "리뷰 본문을 찾을 수 없습니다", receipt_date or "영수증 날짜를 찾을 수 없습니다"
            
        except Exception as e:
            logger.error(f"개별 리뷰 추출 중 오류: {str(e)}")
            return "오류 발생", "오류 발생"

    def extract_review_data_optimized(self, url: str, expected_shop_name: str) -> Tuple[str, str]:
        """
        최적화된 리뷰 데이터 추출 (기존 방식)
        - 업체명을 먼저 찾고, 해당 리뷰의 더보기 버튼만 클릭
        - 업체명 찾으면 스크롤 중단
        """
        try:
            if not self.driver:
                if not self.setup_selenium():
                    return "드라이버 설정 실패", "드라이버 설정 실패"
                    
            # 페이지 로드
            self.driver.get(url)
            
            # 리디렉션 완료 대기 (단축 URL인 경우)
            if "naver.me" in url:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.current_url != url
                )
                logger.info(f"리디렉션 완료: {self.driver.current_url}")
            
            time.sleep(3)  # 초기 페이지 로딩 대기
            
            # 1단계: 먼저 현재 로드된 페이지에서 업체명 찾기
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            target_review = None
            
            # 모든 리뷰 블록 확인
            review_blocks = soup.find_all('div', class_='hahVh2')
            for block in review_blocks:
                shop_elem = block.find('span', class_='pui__pv1E2a')
                if shop_elem and shop_elem.text.strip() == expected_shop_name:
                    target_review = block
                    logger.info(f"업체명 '{expected_shop_name}' 찾음 (스크롤 없이)")
                    break
            
            # 2단계: 못 찾았으면 스크롤하면서 찾기
            if not target_review:
                logger.info("스크롤하면서 업체명 검색 시작")
                scroll_count = 0
                max_scrolls = 10  # 최대 스크롤 횟수 줄임
                
                while scroll_count < max_scrolls:
                    # 스크롤
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # 새로 로드된 부분 확인
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    review_blocks = soup.find_all('div', class_='hahVh2')
                    
                    for block in review_blocks:
                        shop_elem = block.find('span', class_='pui__pv1E2a')
                        if shop_elem and shop_elem.text.strip() == expected_shop_name:
                            target_review = block
                            logger.info(f"업체명 '{expected_shop_name}' 찾음 (스크롤 {scroll_count+1}회)")
                            break
                    
                    if target_review:
                        break
                        
                    scroll_count += 1
            
            # 3단계: 찾은 리뷰에서 데이터 추출
            if target_review:
                review_text = ""
                receipt_date = ""
                
                # 해당 리뷰의 더보기 버튼만 클릭
                try:
                    # 더보기 버튼이 있는지 확인
                    more_button_elem = target_review.find('a', {'data-pui-click-code': 'otherreviewfeed.rvshowmore'})
                    if more_button_elem:
                        # Selenium으로 해당 요소 찾아서 클릭
                        review_blocks_selenium = self.driver.find_elements(By.CSS_SELECTOR, "div.hahVh2")
                        for selenium_block in review_blocks_selenium:
                            if expected_shop_name in selenium_block.text:
                                try:
                                    more_btn = selenium_block.find_element(By.CSS_SELECTOR, "a[data-pui-click-code='otherreviewfeed.rvshowmore']")
                                    if more_btn.is_displayed():
                                        self.driver.execute_script("arguments[0].click();", more_btn)
                                        time.sleep(1)
                                        logger.info("해당 리뷰의 더보기 버튼 클릭")
                                        # 다시 파싱
                                        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                                        # 업체명으로 다시 찾기
                                        review_blocks = soup.find_all('div', class_='hahVh2')
                                        for block in review_blocks:
                                            shop_elem = block.find('span', class_='pui__pv1E2a')
                                            if shop_elem and shop_elem.text.strip() == expected_shop_name:
                                                target_review = block
                                                break
                                    break
                                except:
                                    pass
                except Exception as e:
                    logger.warning(f"더보기 버튼 클릭 중 오류: {str(e)}")
                
                # 리뷰 본문 추출
                review_div = target_review.find('div', class_='pui__vn15t2')
                if review_div:
                    review_text = review_div.text.strip()
                    logger.info(f"리뷰 본문 찾음: {review_text[:50]}...")
                
                # 영수증 날짜 추출
                time_elem = target_review.find('time', {'aria-hidden': 'true'})
                if time_elem:
                    receipt_date = time_elem.text.strip()
                    logger.info(f"영수증 날짜 찾음: {receipt_date}")
                
                return review_text or "리뷰 본문을 찾을 수 없습니다", receipt_date or "영수증 날짜를 찾을 수 없습니다"
            
            else:
                logger.warning(f"업체명 '{expected_shop_name}'과 일치하는 리뷰를 찾지 못했습니다")
                return "일치하는 업체명의 리뷰를 찾을 수 없습니다", "영수증 날짜를 찾을 수 없습니다"
                
        except Exception as e:
            logger.error(f"데이터 추출 중 오류: {str(e)}")
            return "오류 발생", "오류 발생"

    def extract_review(self, url: str, expected_shop_name: Optional[str] = None) -> Tuple[str, str]:
        """
        메인 추출 함수 - URL 타입에 따라 적절한 방법 선택
        """
        try:
            if "/my/review/" in url:
                # 개별 리뷰 페이지 형식 (새로운 형식)
                logger.info("개별 리뷰 페이지 형식으로 처리")
                return self.extract_direct_review(url)
            else:
                # 기존 형식 (naver.me 단축 URL 등)
                logger.info("기존 형식으로 처리")
                if not expected_shop_name:
                    return "업체명이 필요합니다", "업체명이 필요합니다"
                return self.extract_review_data_optimized(url, expected_shop_name)
        except Exception as e:
            logger.error(f"리뷰 추출 중 오류: {str(e)}")
            return "추출 중 오류 발생", "추출 중 오류 발생"
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("셀레니움 드라이버 종료")

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# 편의 함수
def extract_naver_review(url: str, shop_name: Optional[str] = None) -> Tuple[str, str]:
    """
    간단한 리뷰 추출 함수
    """
    with NaverReviewExtractor() as extractor:
        return extractor.extract_review(url, shop_name)