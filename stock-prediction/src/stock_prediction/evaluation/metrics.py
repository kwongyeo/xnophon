"""평가 지표.

예측 지표: IC(Pearson), RankIC(Spearman), 방향 적중률, RMSE.
투자 지표: 누적수익률, 연환산(CAGR), 변동성, 샤프, 최대낙폭(MDD).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ----------------------------------------------------------------- 예측 지표
def information_coefficient(pred, actual) -> float:
    """Pearson IC. 예측값과 실현 수익률의 선형 상관."""
    s = pd.DataFrame({"p": pred, "a": actual}).dropna()
    if len(s) < 3:
        return float("nan")
    return float(s["p"].corr(s["a"]))


def rank_ic(pred, actual) -> float:
    """Spearman RankIC. 순위 상관 — 횡단면 랭킹 모델의 표준 지표."""
    s = pd.DataFrame({"p": pred, "a": actual}).dropna()
    if len(s) < 3:
        return float("nan")
    return float(s["p"].corr(s["a"], method="spearman"))


def directional_accuracy(pred, actual) -> float:
    """부호 일치 비율(상승/하락 방향 적중률)."""
    s = pd.DataFrame({"p": pred, "a": actual}).dropna()
    if s.empty:
        return float("nan")
    return float((np.sign(s["p"]) == np.sign(s["a"])).mean())


def rmse(pred, actual) -> float:
    s = pd.DataFrame({"p": pred, "a": actual}).dropna()
    return float(np.sqrt(((s["p"] - s["a"]) ** 2).mean()))


# ----------------------------------------------------------------- 투자 지표
def sharpe_ratio(returns, freq: int = 252) -> float:
    """주기수익률 시계열의 연환산 샤프(무위험 0 가정)."""
    r = pd.Series(returns).dropna()
    if r.std(ddof=0) == 0 or r.empty:
        return float("nan")
    return float(r.mean() / r.std(ddof=0) * np.sqrt(freq))


def max_drawdown(equity) -> float:
    """누적자산 곡선의 최대낙폭(음수)."""
    e = pd.Series(equity).dropna()
    if e.empty:
        return float("nan")
    peak = e.cummax()
    return float((e / peak - 1).min())


def cagr(equity, periods_per_year: int, n_periods: int) -> float:
    """누적자산 곡선의 연환산 수익률."""
    e = pd.Series(equity).dropna()
    if e.empty or n_periods <= 0:
        return float("nan")
    total = e.iloc[-1] / e.iloc[0]
    years = n_periods / periods_per_year
    return float(total ** (1 / years) - 1) if years > 0 else float("nan")
