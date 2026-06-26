"""미국 시세·재무 수집기 (yfinance).

출력은 schema.PRICE_COLUMNS / FUNDAMENTAL_COLUMNS 로 정규화.
프로토타이핑 단계에서는 MCP UsStockInfo 도구로 대체 가능(docs §1, §2).
"""
from __future__ import annotations

import pandas as pd


def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """일봉 OHLCV(수정주가 포함) 반환.

    구현 예시:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, auto_adjust=True)
    """
    raise NotImplementedError("yfinance 연동 구현 예정 — docs/data-sources.md §1 참조")


def fetch_financials(ticker: str) -> pd.DataFrame:
    """분기 재무제표 → FUNDAMENTAL_COLUMNS. disclosed_at 시점 정렬 필수."""
    raise NotImplementedError
