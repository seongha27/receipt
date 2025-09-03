import pandas as pd
import os
from datetime import datetime, timedelta

def parse_excel_file(file_path):
    """엑셀 파일을 파싱하여 데이터 추출"""
    try:
        # 파일 확장자에 따라 읽기
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        elif ext == '.csv':
            # 한글 인코딩 처리
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except:
                df = pd.read_csv(file_path, encoding='cp949')
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {ext}")
        
        # 컬럼명 정규화
        df.columns = df.columns.str.strip()
        
        # 필수 컬럼 확인
        required_columns = ['번호', '날짜']
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"필수 컬럼 '{col}'이 없습니다.")
        
        # 데이터 정리
        result = []
        for idx, row in df.iterrows():
            item = {
                '번호': int(row['번호']),
                '날짜': pd.to_datetime(row['날짜']).strftime('%Y-%m-%d'),
                '리뷰내용': str(row.get('리뷰내용', '')).strip() if pd.notna(row.get('리뷰내용', '')) else '',
                '사진번호': int(row['사진번호']) if pd.notna(row.get('사진번호', '')) else None
            }
            result.append(item)
        
        return sorted(result, key=lambda x: x['번호'])
        
    except Exception as e:
        raise Exception(f"엑셀 파일 읽기 오류: {str(e)}")

def create_excel_template():
    """엑셀 템플릿 생성"""
    # 샘플 데이터
    sample_data = []
    date_start = datetime(2025, 7, 29)
    
    for day in range(7):  # 7일
        current_date = date_start + timedelta(days=day)
        for i in range(5):  # 하루 5개
            num = day * 5 + i + 1
            item = {
                '번호': f'{num:03d}',
                '날짜': current_date.strftime('%Y-%m-%d'),
                '리뷰내용': f'{num}번째 리뷰 내용입니다.' if num <= 10 else '',
                '사진번호': num if num <= 7 else ''
            }
            sample_data.append(item)
    
    df = pd.DataFrame(sample_data)
    
    # 엑셀 파일 생성
    with pd.ExcelWriter('영수증_데이터_템플릿.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='데이터', index=False)
        
        # 설명 시트 추가
        instruction = pd.DataFrame({
            '항목': ['번호', '날짜', '리뷰내용', '사진번호'],
            '설명': [
                '001, 002, 003 형식으로 입력 (필수)',
                'YYYY-MM-DD 형식으로 입력 (필수)',
                '리뷰 내용 입력 (선택)',
                '사진 업로드 순서 번호 입력 (선택)'
            ],
            '예시': ['001', '2025-07-29', '음식이 맛있어요', '1']
        })
        instruction.to_excel(writer, sheet_name='사용법', index=False)
    
    # CSV 파일 생성 (한셀용)
    df.to_csv('영수증_데이터_템플릿.csv', index=False, encoding='utf-8-sig')
    
    print("템플릿 파일 생성 완료:")
    print("- 영수증_데이터_템플릿.xlsx (엑셀)")
    print("- 영수증_데이터_템플릿.csv (한셀)")

if __name__ == '__main__':
    create_excel_template()