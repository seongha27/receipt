import requests
from bs4 import BeautifulSoup
import logging
from typing import Tuple, Optional
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleNaverReviewExtractor:
    """Chrome 없이 작동하는 간단한 리뷰 추출기"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def extract_review(self, url: str, expected_shop_name: Optional[str] = None) -> Tuple[str, str]:
        """
        간단한 리뷰 추출 (Selenium 없이)
        """
        try:
            logger.info(f"리뷰 추출 시작: {url}")
            
            # HTTP 요청으로 페이지 가져오기
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 기본 메타데이터 추출 시도
            review_text = "웹 스크래핑으로 추출된 기본 리뷰 정보"
            receipt_date = "날짜 정보 없음"
            
            # 페이지 제목에서 업체명 추출 시도
            title = soup.find('title')
            if title:
                title_text = title.get_text().strip()
                logger.info(f"페이지 제목: {title_text}")
                
            # 메타 태그에서 설명 추출 시도
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                review_text = meta_desc.get('content', '')[:200] + "..."
                
            logger.info("리뷰 추출 완료 (기본 정보)")
            return review_text, receipt_date
            
        except Exception as e:
            logger.error(f"리뷰 추출 오류: {str(e)}")
            return f"추출 실패: {str(e)}", "오류 발생"

# 편의 함수
def extract_naver_review_simple(url: str, shop_name: Optional[str] = None) -> Tuple[str, str]:
    """
    간단한 리뷰 추출 함수 (Chrome 불필요)
    """
    extractor = SimpleNaverReviewExtractor()
    return extractor.extract_review(url, shop_name)