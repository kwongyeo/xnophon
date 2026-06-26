"""백테스트 엔진: 모델 예측 → 상위 K종목 동일가중 롱 → 거래비용 차감 수익률.

입력은 out-of-sample 예측 long 프레임:
    columns = [date, ticker, pred, fwd_ret]
      pred    : 모델 점수(클수록 매수 매력)
      fwd_ret : 해당 시점의 실현 미래 h일 수익률(타깃)

겹침(overlap) 없는 평가를 위해 h 거래일마다 리밸런싱한다(논오버랩).
각 리밸런싱일: pred 상위 top_k 동일가중 → 평균 fwd_ret - 왕복비용.
벤치마크: 같은 날 전체 종목 동일가중(equal-weight) 수익률.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..evaluation import metrics


def run_backtest(pred_df: pd.DataFrame, horizon: int, top_k: int,
                 cost_bps: float = 25.0) -> dict:
    df = pred_df.dropna(subset=["pred", "fwd_ret"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    dates = np.sort(df["date"].unique())

    # h 거래일 간격으로 논오버랩 리밸런싱일 선택
    rebal_dates = dates[::horizon]
    cost = cost_bps / 1e4  # 왕복 거래비용 (비율)

    rows = []
    for d in rebal_dates:
        day = df[df["date"] == d]
        if len(day) < max(top_k, 2):
            continue
        picks = day.nlargest(top_k, "pred")
        strat_ret = picks["fwd_ret"].mean() - cost
        bench_ret = day["fwd_ret"].mean()
        rows.append({"date": d, "strat_ret": strat_ret, "bench_ret": bench_ret,
                     "n": len(day)})

    bt = pd.DataFrame(rows)
    if bt.empty:
        return {"error": "리밸런싱 가능한 날짜 없음(데이터 부족)"}

    bt["strat_equity"] = (1 + bt["strat_ret"]).cumprod()
    bt["bench_equity"] = (1 + bt["bench_ret"]).cumprod()

    ppy = 252 / horizon  # 연간 리밸런싱 횟수
    n = len(bt)

    def perf(ret_col, eq_col):
        return {
            "total_return": float(bt[eq_col].iloc[-1] - 1),
            "cagr": metrics.cagr(bt[eq_col], ppy, n),
            "sharpe": metrics.sharpe_ratio(bt[ret_col], freq=ppy),
            "mdd": metrics.max_drawdown(bt[eq_col]),
            "hit": float((bt[ret_col] > 0).mean()),
        }

    return {
        "n_rebalances": n,
        "ic": metrics.information_coefficient(df["pred"], df["fwd_ret"]),
        "rank_ic": metrics.rank_ic(df["pred"], df["fwd_ret"]),
        "dir_acc": metrics.directional_accuracy(df["pred"], df["fwd_ret"]),
        "strategy": perf("strat_ret", "strat_equity"),
        "benchmark": perf("bench_ret", "bench_equity"),
        "curve": bt,
    }
