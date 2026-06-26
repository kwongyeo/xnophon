"""한국 시세 수집기 (KRX).

1순위: pykrx, 대안: FinanceDataReader. 출력은 schema.PRICE_COLUMNS 로 정규화.
"""
from __future__ import annotations

import pandas as pd


def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """한 종목의 일봉 OHLCV를 표준 스키마로 반환.

    구현 예시 (pykrx):
        from pykrx import stock
        df = stock.get_market_ohlcv(start, end, ticker)
        # → 컬럼명 매핑 후 adj_close/market_cap 결합 → PRICE_COLUMNS 정렬
    """
    raise NotImplementedError("pykrx 연동 구현 예정 — docs/data-sources.md §1 참조")


def list_index_components(index: str) -> list[str]:
    """지수(KOSPI200 등) 구성종목 코드 목록. 유니버스 정의에 사용."""
    raise NotImplementedError
