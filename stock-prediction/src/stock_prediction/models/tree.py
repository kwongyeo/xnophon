"""그래디언트 부스팅 모델 (LightGBM). 표 형태 피처에 강력한 1순위 후보.

회귀(미래수익률 예측)로 사용. config.model.params 로 하이퍼파라미터 주입.
"""
from __future__ import annotations

import numpy as np


class TreeModel:
    def __init__(self, params: dict | None = None, seed: int = 42):
        import lightgbm as lgb

        p = dict(params or {})
        self._lgb = lgb
        self.params = {
            "objective": "regression",
            "n_estimators": p.get("n_estimators", 500),
            "learning_rate": p.get("learning_rate", 0.03),
            "max_depth": p.get("max_depth", 6),
            "subsample": p.get("subsample", 0.8),
            "num_leaves": p.get("num_leaves", 31),
            "min_child_samples": p.get("min_child_samples", 20),
            "random_state": seed,
            "n_jobs": -1,
            "verbose": -1,
        }
        self.model = lgb.LGBMRegressor(**self.params)

    def fit(self, X, y):
        self.model.fit(X, y)
        return self

    def predict(self, X):
        return np.asarray(self.model.predict(X))
