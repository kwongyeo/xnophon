"""미국(및 yfinance 호환) 시세·재무 수집기.

두 경로를 제공한다:
- fetch_*  : 운영 경로. yfinance 라이브러리로 직접 수집(인터넷 필요).
- normalize_* : 이미 받은 원본 JSON(MCP UsStockInfo 또는 yfinance 덤프)을 표준 스키마로 변환.

⚠️ 일부 샌드박스 환경은 Yahoo Finance 직접 접속이 프록시에서 차단된다.
   그 경우 MCP 도구(UsStockInfo)로 원본을 받아 data/raw 에 저장한 뒤 normalize_* 를 사용한다.
   yfinance 시세는 한국 종목도 지원한다(예: 삼성전자 = "005930.KS").
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..schema import FUNDAMENTAL_COLUMNS, PRICE_COLUMNS


# ---------------------------------------------------------------- 운영 경로
def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """yfinance로 일봉(수정주가 포함)을 받아 표준 스키마로 반환."""
    import yfinance as yf  # 지연 import — 미설치/오프라인 환경 대비

    raw = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
    raw = raw.reset_index()
    df = pd.DataFrame()
    df["date"] = pd.to_datetime(raw["Date"])
    df["ticker"] = ticker
    df["open"] = raw["Open"]
    df["high"] = raw["High"]
    df["low"] = raw["Low"]
    df["close"] = raw["Close"]
    df["adj_close"] = raw.get("Adj Close", raw["Close"])
    df["volume"] = raw["Volume"]
    df["value"] = raw["Close"] * raw["Volume"]
    df["market_cap"] = pd.NA
    return df[PRICE_COLUMNS]


# ---------------------------------------------------------------- 원본 정규화
def _unwrap(raw: str | dict | list) -> list[dict]:
    """MCP 응답({"result": "<json>"}) 또는 직접 JSON을 레코드 리스트로 푼다."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict) and "result" in raw:
        raw = raw["result"]
        if isinstance(raw, str):
            raw = json.loads(raw)
    return raw


def normalize_price(raw: str | dict | list, ticker: str) -> pd.DataFrame:
    """UsStockInfo/yfinance 시세 원본을 PRICE_COLUMNS 로 변환.

    원본 레코드: {Date, Open, High, Low, Close, Volume, Dividends, Stock Splits}
    주의: MCP 응답에는 Adj Close 가 없어 close 로 대체한다(운영에서는 수정주가 사용 권장).
    """
    records = _unwrap(raw)
    r = pd.DataFrame(records)
    df = pd.DataFrame()
    df["date"] = pd.to_datetime(r["Date"]).dt.tz_localize(None).dt.normalize()
    df["ticker"] = ticker
    df["open"] = r["Open"].astype(float)
    df["high"] = r["High"].astype(float)
    df["low"] = r["Low"].astype(float)
    df["close"] = r["Close"].astype(float)
    df["adj_close"] = r.get("Adj Close", r["Close"]).astype(float)
    df["volume"] = r["Volume"].astype("int64")
    df["value"] = (df["close"] * df["volume"]).astype(float)
    df["market_cap"] = pd.NA
    return df[PRICE_COLUMNS].sort_values("date").reset_index(drop=True)


def normalize_financials(income: str | dict | list,
                         balance: str | dict | list,
                         ticker: str) -> pd.DataFrame:
    """분기 손익 + 재무상태표 원본을 FUNDAMENTAL_COLUMNS 로 변환(분기별 1행)."""
    inc = {row["date"]: row for row in _unwrap(income)}
    bal = {row["date"]: row for row in _unwrap(balance)}
    rows = []
    for date in sorted(set(inc) | set(bal)):
        i, b = inc.get(date, {}), bal.get(date, {})
        rows.append({
            "ticker": ticker,
            "fiscal_period": date,
            # yfinance 원본은 보고서 공개일을 주지 않는다. 운영에서는 SEC EDGAR filing date로
            # 보정해야 하며, 보수적으로 분기말+45일을 disclosed_at 근사치로 둔다.
            "disclosed_at": (pd.to_datetime(date) + pd.Timedelta(days=45)).date().isoformat(),
            "revenue": i.get("Total Revenue"),
            "operating_income": i.get("Operating Income"),
            "net_income": i.get("Net Income"),
            "total_assets": b.get("Total Assets"),
            "total_equity": b.get("Stockholders Equity") or b.get("Total Equity Gross Minority Interest"),
            "total_debt": b.get("Total Debt"),
        })
    return pd.DataFrame(rows)[FUNDAMENTAL_COLUMNS]


def load_raw(path: str | Path) -> str:
    """data/raw 의 원본 JSON 텍스트를 그대로 읽는다."""
    return Path(path).read_text(encoding="utf-8")
