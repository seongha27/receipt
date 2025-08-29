import gspread
from google.oauth2.service_account import Credentials
import logging
import json
import os
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self, credentials_file_path: Optional[str] = None):
        self.client = None
        self.sheet = None
        self.credentials_file_path = credentials_file_path or "credentials.json"
        
    def setup_google_sheets(self, sheet_id: str, sheet_name: str = "영수증리뷰관리"):
        """구글 스프레드시트 연결 설정"""
        try:
            # 인증 정보가 환경변수에 있는지 확인
            google_credentials = os.getenv('GOOGLE_CREDENTIALS')
            if google_credentials:
                # 환경변수에서 JSON 읽기
                credentials_info = json.loads(google_credentials)
                scope = ['https://spreadsheets.google.com/feeds',
                        'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
            elif os.path.exists(self.credentials_file_path):
                # 파일에서 인증 정보 읽기
                scope = ['https://spreadsheets.google.com/feeds',
                        'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_file(self.credentials_file_path, scopes=scope)
            else:
                logger.error("구글 인증 파일을 찾을 수 없습니다")
                return False
            
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(sheet_id).worksheet(sheet_name)
            
            logger.info("구글 스프레드시트 연결 성공")
            return True
            
        except Exception as e:
            logger.error(f"구글 스프레드시트 연결 실패: {str(e)}")
            return False

    def read_all_data(self) -> List[List[str]]:
        """스프레드시트 전체 데이터 읽기"""
        try:
            if not self.sheet:
                return []
            
            all_values = self.sheet.get_all_values()
            logger.info(f"스프레드시트에서 {len(all_values)} 행을 가져왔습니다")
            return all_values
            
        except Exception as e:
            logger.error(f"데이터 읽기 실패: {str(e)}")
            return []

    def update_review_data(self, row_idx: int, review_text: str, receipt_date: str, 
                          registration_date: Optional[str] = None, status: str = "완료"):
        """리뷰 데이터를 스프레드시트에 업데이트"""
        try:
            if not self.sheet:
                return False
            
            # C열(3)에 리뷰본문, D열(4)에 영수증날짜
            self.sheet.update_cell(row_idx, 3, review_text)
            self.sheet.update_cell(row_idx, 4, receipt_date)
            
            # E열(5)에 등록일
            if not registration_date:
                registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.sheet.update_cell(row_idx, 5, registration_date)
            
            # F열(6)에 상태
            self.sheet.update_cell(row_idx, 6, status)
            
            logger.info(f"{row_idx}행 업데이트 완료")
            time.sleep(1)  # API 제한 방지
            return True
            
        except Exception as e:
            logger.error(f"{row_idx}행 업데이트 실패: {str(e)}")
            try:
                self.sheet.update_cell(row_idx, 6, "실패")
            except:
                pass
            return False

    def add_new_review(self, store_name: str, review_url: str, review_text: str = "", 
                      receipt_date: str = "", status: str = "대기"):
        """새 리뷰를 스프레드시트에 추가"""
        try:
            if not self.sheet:
                return False
            
            # 마지막 행 다음에 데이터 추가
            next_row = len(self.sheet.get_all_values()) + 1
            
            row_data = [
                store_name,  # A열: 업체명
                review_url,  # B열: 리뷰URL
                review_text,  # C열: 리뷰본문
                receipt_date,  # D열: 영수증날짜
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # E열: 등록일
                status  # F열: 상태
            ]
            
            self.sheet.insert_row(row_data, next_row)
            logger.info(f"새 리뷰 추가 완료: {store_name} - 행 {next_row}")
            return next_row
            
        except Exception as e:
            logger.error(f"새 리뷰 추가 실패: {str(e)}")
            return False

    def get_pending_reviews(self) -> List[Dict]:
        """처리 대기중인 리뷰 목록 반환"""
        try:
            if not self.sheet:
                return []
            
            all_values = self.sheet.get_all_values()
            pending_reviews = []
            
            # 헤더 제외하고 처리
            for idx, row in enumerate(all_values[1:], start=2):
                if len(row) < 2:
                    continue
                    
                store_name = row[0] if len(row) > 0 else ""
                review_url = row[1] if len(row) > 1 else ""
                review_text = row[2] if len(row) > 2 else ""
                receipt_date = row[3] if len(row) > 3 else ""
                status = row[5] if len(row) > 5 else ""
                
                # URL이 있고 아직 처리되지 않은 경우
                if review_url and not review_text and status != "완료":
                    pending_reviews.append({
                        "row": idx,
                        "store_name": store_name,
                        "review_url": review_url,
                        "status": status or "대기"
                    })
            
            logger.info(f"대기중인 리뷰 {len(pending_reviews)}개 발견")
            return pending_reviews
            
        except Exception as e:
            logger.error(f"대기 리뷰 조회 실패: {str(e)}")
            return []

    def sync_review_to_sheet(self, review_data: Dict) -> bool:
        """리뷰 데이터를 구글 시트에 동기화"""
        try:
            if review_data.get('google_sheet_row'):
                # 기존 행 업데이트
                return self.update_review_data(
                    review_data['google_sheet_row'],
                    review_data.get('extracted_review_text', ''),
                    review_data.get('extracted_receipt_date', ''),
                    status="완료" if review_data.get('status') == 'completed' else "처리중"
                )
            else:
                # 새 행 추가
                return self.add_new_review(
                    review_data.get('store_name', ''),
                    review_data.get('review_url', ''),
                    review_data.get('extracted_review_text', ''),
                    review_data.get('extracted_receipt_date', ''),
                    "완료" if review_data.get('status') == 'completed' else "처리중"
                )
        except Exception as e:
            logger.error(f"시트 동기화 실패: {str(e)}")
            return False

    def test_connection(self) -> Dict:
        """연결 테스트"""
        try:
            if not self.client:
                return {"success": False, "message": "클라이언트가 초기화되지 않았습니다"}
            
            # 시트 접근 테스트
            sheet_info = {
                "title": self.sheet.spreadsheet.title if self.sheet else "알 수 없음",
                "worksheet_count": len(self.sheet.spreadsheet.worksheets()) if self.sheet else 0,
                "current_sheet": self.sheet.title if self.sheet else "알 수 없음",
                "row_count": len(self.sheet.get_all_values()) if self.sheet else 0
            }
            
            return {"success": True, "message": "연결 성공", "sheet_info": sheet_info}
            
        except Exception as e:
            return {"success": False, "message": f"연결 테스트 실패: {str(e)}"}

# 편의 함수
def create_google_sheets_service(sheet_id: str, credentials_file: Optional[str] = None) -> Optional[GoogleSheetsService]:
    """구글 시트 서비스 생성"""
    try:
        service = GoogleSheetsService(credentials_file)
        if service.setup_google_sheets(sheet_id):
            return service
        return None
    except Exception as e:
        logger.error(f"구글 시트 서비스 생성 실패: {e}")
        return None