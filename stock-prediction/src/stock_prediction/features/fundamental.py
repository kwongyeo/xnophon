"""펀더멘털 피처: PER/PBR/PSR, ROE/ROA, 부채비율, 매출·이익 성장률.
재무는 point-in-time(disclosed_at) 정렬 후 가격에 forward-fill 조인.
"""
from __future__ import annotations

import pandas as pd


def add_fundamental_features(prices: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError
