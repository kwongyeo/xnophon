"""기술적 피처: 이동평균, 모멘텀(RSI), MACD, 볼린저밴드, 실현변동성, 거래량 z-score 등.
모든 피처는 과거 윈도만 사용(rolling, shift) — 미래 데이터 금지.
"""
from __future__ import annotations

import pandas as pd


def add_technical_features(prices: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError
