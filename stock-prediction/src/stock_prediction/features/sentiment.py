"""심리 피처: 일별 기사량 스파이크, 평균 감성 점수, 검색량 변화.
감성 점수는 KR-FinBERT 등 금융 감성모델로 산출(단계 4).
"""
from __future__ import annotations

import pandas as pd


def add_sentiment_features(prices: pd.DataFrame, sentiment: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError
