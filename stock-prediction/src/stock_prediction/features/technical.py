"""기술적 피처: 일간수익률, 이동평균, 모멘텀(RSI), 실현변동성, 거래량 z-score.

모든 피처는 과거 윈도만 사용(rolling/shift) — 미래 데이터 금지(look-ahead 방지).
입력: schema.PRICE_COLUMNS (종목별 정렬됨). 출력: 피처 컬럼이 추가된 동일 프레임.
"""
from __future__ import annotations

import pandas as pd


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - 100 / (1 + rs)


def add_technical_features(prices: pd.DataFrame) -> pd.DataFrame:
    """종목 하나의 가격 프레임에 기술적 피처를 추가한다."""
    df = prices.sort_values("date").copy()
    px = df["adj_close"]

    df["ret_1d"] = px.pct_change()
    df["ma_5"] = px.rolling(5).mean()
    df["ma_20"] = px.rolling(20).mean()
    df["ma_ratio"] = df["ma_5"] / df["ma_20"]          # 단기/장기 추세
    df["mom_20"] = px.pct_change(20)                     # 20일 모멘텀
    df["vol_20"] = df["ret_1d"].rolling(20).std()       # 실현변동성
    df["rsi_14"] = _rsi(px, 14)
    vol_mean = df["volume"].rolling(20).mean()
    vol_std = df["volume"].rolling(20).std()
    df["volume_z"] = (df["volume"] - vol_mean) / vol_std  # 거래량 급증 신호
    return df


FEATURE_COLUMNS = ["ret_1d", "ma_ratio", "mom_20", "vol_20", "rsi_14", "volume_z"]
