"""표준 데이터 스키마.

모든 수집기(collector)는 소스가 무엇이든 아래 표준 컬럼으로 정규화해 반환한다.
다운스트림(피처/모델)은 소스를 몰라도 되도록 스키마를 단일 계약으로 유지한다.
"""
from __future__ import annotations

# 가격 (일봉) — collectors.* 의 공통 출력
PRICE_COLUMNS = [
    "date",        # datetime64, 거래일 (영업일)
    "ticker",      # str, 종목코드
    "open",
    "high",
    "low",
    "close",
    "adj_close",   # 수정주가 (배당·분할 반영) — 수익률 계산은 이 컬럼 기준
    "volume",
    "value",       # 거래대금
    "market_cap",
]

# 재무 — point-in-time. disclosed_at 이전 시점에 사용 금지.
FUNDAMENTAL_COLUMNS = [
    "ticker",
    "fiscal_period",  # 예: 2024Q1
    "disclosed_at",   # ★ 공시 공개일. 피처 조인은 disclosed_at <= t 조건만.
    "revenue",
    "operating_income",
    "net_income",
    "total_assets",
    "total_equity",
    "total_debt",
]

# 심리 — 발행 시각 이전 사용 금지.
SENTIMENT_COLUMNS = [
    "date",
    "ticker",
    "article_count",  # 일별 기사 수 (관심도)
    "sentiment",      # 일별 평균 감성 [-1, 1]
]
