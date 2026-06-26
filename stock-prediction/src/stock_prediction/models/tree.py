"""그래디언트 부스팅 모델 (LightGBM / XGBoost). 표 형태 피처에 강력한 1순위 후보."""
from __future__ import annotations


class TreeModel:
    """config.model.params 로 초기화. 횡단면 랭킹/회귀에 사용."""
    def __init__(self, params: dict): self.params = params
    def fit(self, X, y): raise NotImplementedError
    def predict(self, X): raise NotImplementedError
