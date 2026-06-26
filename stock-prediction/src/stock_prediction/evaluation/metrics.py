"""평가 지표.

예측 지표: IC(정보계수), RankIC, 정확도/AUC(분류), RMSE(회귀).
투자 지표: 누적수익률, 연환산수익률, 변동성, 샤프, 최대낙폭(MDD), 회전율.
"""
from __future__ import annotations


def information_coefficient(pred, actual) -> float:
    raise NotImplementedError


def sharpe_ratio(returns, freq: int = 252) -> float:
    raise NotImplementedError
