def extract_receipt_date_from_block(review_block):
    """특정 리뷰 블록에서만 영수증 날짜 추출 (영수증 컨텍스트 + datetime 우선)"""
    try:
        logging.info("=== 리뷰 블록에서 날짜 추출 시작 ===")

        # 0) 도우미
        def norm(s: str) -> str:
            if not s: return ""
            s = re.sub(r"\s+", "", s)
            s = s.replace("(", "").replace(")", "")
            s = s.replace("·", ".").replace("ㆍ", ".")
            return s

        def is_receipt_like(txt: str) -> bool:
            if not txt: return False
            pats = [
                r"\d{1,2}\.\d{1,2}\.[월화수목금토일]",               # 8.30.토
                r"\d{1,2}\.\d{1,2}\.\s*[\(]?[월화수목금토일][\)]?",  # 8.30.(토), 8.30. 토
                r"20\d{2}\.\d{1,2}\.\d{1,2}\.?\s*[\(]?[월화수목금토일]?[\)]?",  # 2025.08.30.(토)
                r"\d{1,2}/\d{1,2}\([월화수목금토일]\)",               # 8/30(토)
                r"20\d{2}/\d{1,2}/\d{1,2}\([월화수목금토일]\)",       # 2025/8/30(토)
            ]
            n = norm(txt)
            return any(re.search(p, n) for p in pats)

        # 1) 블록 내 <time> 싹 수집
        time_elements = review_block.find_all('time')
        logging.info(f"해당 리뷰 블록에서 발견된 time 요소 개수: {len(time_elements)}")

        # 2) '영수증' 텍스트 **근처**의 time 최우선 (부모/조상 텍스트 활용)
        receipt_candidates = []
        for t in time_elements:
            try:
                parent = t.parent
                ctx_txt = ""
                # 부모~조상 2~3단계 텍스트 모아 컨텍스트 판단
                hops = 0
                while parent is not None and hops < 3:
                    ctx_txt += " " + (parent.get_text(" ", strip=True) or "")
                    parent = parent.parent
                    hops += 1
                score = 0
                if "영수증" in ctx_txt:
                    score += 20
                # 요일 포함 형식이면 가산점
                if is_receipt_like(t.get_text(strip=True)):
                    score += 10
                # datetime 있으면 더 가산 (가장 신뢰)
                dt = (t.get("datetime") or "").strip()
                if re.search(r"20\d{2}-\d{2}-\d{2}", dt):
                    score += 30
                if score > 0:
                    receipt_candidates.append((score, t))
            except Exception:
                continue

        if receipt_candidates:
            receipt_candidates.sort(key=lambda x: x[0], reverse=True)
            top = receipt_candidates[0][1]
            txt = top.get_text(strip=True) or top.get("datetime") or ""
            logging.info(f"  ✅ 컨텍스트 기반 선택: {txt}")
            return txt or "영수증 날짜를 찾을 수 없습니다"

        # 3) 컨텍스트가 없으면: datetime 있는 time 우선 선택
        dt_cands = []
        for t in time_elements:
            dt = (t.get("datetime") or "").strip()
            if re.search(r"20\d{2}-\d{2}-\d{2}", dt):
                # 날짜 텍스트도 함께 확인해서 영수증스러운 것에 가점
                score = 10
                if is_receipt_like(t.get_text(strip=True)):
                    score += 5
                dt_cands.append((score, t))
        if dt_cands:
            dt_cands.sort(key=lambda x: x[0], reverse=True)
            top = dt_cands[0][1]
            txt = top.get_text(strip=True) or top.get("datetime") or ""
            logging.info(f"  ✅ datetime 기반 선택: {txt}")
            return txt or "영수증 날짜를 찾을 수 없습니다"

        # 4) 여전히 없으면: 블록 내 time들 중 '영수증스러운' 형식 우선
        for t in time_elements:
            txt = t.get_text(strip=True)
            if is_receipt_like(txt):
                logging.info(f"  ✅ 패턴 기반 선택: {txt}")
                return txt

        # 5) 마지막 최후의 보루: aria-hidden / 첫 번째 time
        t = review_block.find('time', {'aria-hidden': 'true'})
        if t and (t.get_text(strip=True)):
            logging.info(f"  fallback aria-hidden: {t.get_text(strip=True)}")
            return t.get_text(strip=True)

        if time_elements:
            logging.info(f"  fallback first time: {time_elements[0].get_text(strip=True)}")
            return time_elements[0].get_text(strip=True)

        logging.info("=== 최종: 영수증 날짜를 찾을 수 없습니다 ===")
        return "영수증 날짜를 찾을 수 없습니다"

    except Exception as e:
        logging.error(f"영수증 날짜 추출 중 오류: {str(e)}")
        return "날짜 추출 실패"
