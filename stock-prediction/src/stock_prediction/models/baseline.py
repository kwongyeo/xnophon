"""기준 모델: naive(전일 수익률 유지), 횡단면 평균, 로지스틱/선형 회귀.
모든 고급 모델은 이 베이스라인을 이겨야 의미가 있다.
"""
from __future__ import annotations


class BaselineModel:
    def fit(self, X, y): raise NotImplementedError
    def predict(self, X): raise NotImplementedError
