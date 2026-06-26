"""기준(baseline) 모델들. 고급 모델은 이들을 이겨야 의미가 있다.

- MomentumBaseline: 학습 불필요. 최근 모멘텀(mom_20)을 그대로 예측 점수로 사용.
- RidgeModel: 선형 회귀 베이스라인(피처 표준화 포함).

공통 인터페이스: fit(X, y) / predict(X) — X는 (n, p) ndarray, 반환은 (n,) 점수.
점수는 '클수록 매수 매력' 의미. 백테스트는 점수 상위 K종목을 롱한다.
"""
from __future__ import annotations

import numpy as np


class MomentumBaseline:
    """무학습 기준선. momentum 피처 컬럼을 점수로 그대로 사용."""

    def __init__(self, mom_index: int = 0):
        self.mom_index = mom_index  # X에서 모멘텀 피처의 열 위치

    def fit(self, X, y):
        return self

    def predict(self, X):
        return np.asarray(X)[:, self.mom_index]


class RidgeModel:
    """표준화 + Ridge 회귀 선형 베이스라인."""

    def __init__(self, alpha: float = 1.0):
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        self.model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))

    def fit(self, X, y):
        self.model.fit(X, y)
        return self

    def predict(self, X):
        return self.model.predict(X)
