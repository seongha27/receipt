from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
import logging
import time
import os
from typing import Tuple, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FullNaverReviewExtractor:
    def __init__(self):
        self.driver = None
        self.chrome_available = False
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def setup_selenium(self):
        """셀레니움 크롬 드라이버 설정"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 서버 환경에서 Chrome 바이너리 경로
            chrome_binary = os.getenv('GOOGLE_CHROME_BIN')
            if chrome_binary:
                options.binary_location = chrome_binary
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.implicitly_wait(5)
            self.chrome_available = True
            
            logger.info("셀레니움 드라이버 설정 완료")
            return True
        except Exception as e:
            logger.warning(f"셀레니움 드라이버 설정 실패: {str(e)}")
            logger.info("HTTP 요청 방식으로 대체 실행합니다")
            self.chrome_available = False
            return False

    def extract_direct_review(self, url: str) -> Tuple[str, str]:
        """개별 리뷰 페이지에서 직접 추출 (새로운 링크 형식)"""
        if not self.chrome_available:
            return self.extract_with_requests(url)
            
        try:
            if not self.driver:
                if not self.setup_selenium():
                    return self.extract_with_requests(url)
                    
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
        """최적화된 리뷰 데이터 추출 (기존 방식)"""
        if not self.chrome_available:
            return self.extract_with_requests(url)
            
        try:
            if not self.driver:
                if not self.setup_selenium():
                    return self.extract_with_requests(url)
                    
            # 페이지 로드
            self.driver.get(url)
            
            # 리디렉션 완료 대기 (단축 URL인 경우)
            if "naver.me" in url:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.current_url != url
                )
                logger.info(f"리디렉션 완료: {self.driver.current_url}")
            
            time.sleep(3)
            
            # 업체명으로 리뷰 찾기
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            target_review = None
            
            # 모든 리뷰 블록 확인
            review_blocks = soup.find_all('div', class_='hahVh2')
            for block in review_blocks:
                shop_elem = block.find('span', class_='pui__pv1E2a')
                if shop_elem and shop_elem.text.strip() == expected_shop_name:
                    target_review = block
                    logger.info(f"업체명 '{expected_shop_name}' 찾음")
                    break
            
            # 스크롤해서 찾기
            if not target_review:
                logger.info("스크롤하면서 업체명 검색")
                for _ in range(5):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    review_blocks = soup.find_all('div', class_='hahVh2')
                    
                    for block in review_blocks:
                        shop_elem = block.find('span', class_='pui__pv1E2a')
                        if shop_elem and shop_elem.text.strip() == expected_shop_name:
                            target_review = block
                            break
                    
                    if target_review:
                        break
            
            # 데이터 추출
            if target_review:
                review_text = ""
                receipt_date = ""
                
                # 리뷰 본문 추출
                review_div = target_review.find('div', class_='pui__vn15t2')
                if review_div:
                    review_text = review_div.text.strip()
                
                # 영수증 날짜 추출
                time_elem = target_review.find('time', {'aria-hidden': 'true'})
                if time_elem:
                    receipt_date = time_elem.text.strip()
                
                return review_text or "리뷰 본문을 찾을 수 없습니다", receipt_date or "영수증 날짜를 찾을 수 없습니다"
            else:
                logger.warning(f"업체명 '{expected_shop_name}'과 일치하는 리뷰를 찾지 못했습니다")
                return "일치하는 업체명의 리뷰를 찾을 수 없습니다", "영수증 날짜를 찾을 수 없습니다"
                
        except Exception as e:
            logger.error(f"데이터 추출 중 오류: {str(e)}")
            return "오류 발생", "오류 발생"

    def extract_with_requests(self, url: str) -> Tuple[str, str]:
        """HTTP 요청으로 기본 정보 추출 (Chrome 없을 때)"""
        try:
            logger.info(f"HTTP 요청으로 페이지 접근: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 기본 정보 추출
            title = soup.find('title')
            title_text = title.get_text() if title else "제목 없음"
            
            # 메타 태그에서 설명 추출
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ""
            
            review_text = f"페이지 제목: {title_text}\n설명: {description[:100]}..."
            receipt_date = "HTTP 추출 - 날짜 정보 제한됨"
            
            return review_text, receipt_date
            
        except Exception as e:
            logger.error(f"HTTP 추출 오류: {str(e)}")
            return f"HTTP 추출 실패: {str(e)}", "오류 발생"

    def extract_review(self, url: str, expected_shop_name: Optional[str] = None) -> Tuple[str, str]:
        """메인 추출 함수 - URL 타입에 따라 적절한 방법 선택"""
        try:
            if "/my/review/" in url:
                # 개별 리뷰 페이지 형식
                logger.info("개별 리뷰 페이지 형식으로 처리")
                return self.extract_direct_review(url)
            else:
                # 기존 형식 (naver.me 단축 URL 등)
                logger.info("기존 형식으로 처리")
                if not expected_shop_name:
                    # 업체명이 없으면 HTTP 방식으로
                    return self.extract_with_requests(url)
                return self.extract_review_data_optimized(url, expected_shop_name)
        except Exception as e:
            logger.error(f"리뷰 추출 중 오류: {str(e)}")
            return "추출 중 오류 발생", "추출 중 오류 발생"
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# 편의 함수
def extract_naver_review_full(url: str, shop_name: Optional[str] = None) -> Tuple[str, str]:
    """완전한 리뷰 추출 함수"""
    with FullNaverReviewExtractor() as extractor:
        return extractor.extract_review(url, shop_name)