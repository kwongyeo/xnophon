"""백테스트 엔진: 모델 예측 → 상위 K종목 동일가중 롱 → 거래비용 차감 수익률.

입력은 out-of-sample 예측 long 프레임:
    columns = [date, ticker, pred, fwd_ret]
      pred    : 모델 점수(클수록 매수 매력)
      fwd_ret : 해당 시점의 실현 미래 h일 수익률(타깃)

겹침(overlap) 없는 평가를 위해 h 거래일마다 리밸런싱한다(논오버랩).

모드:
- long(기본): pred 상위 top_k 동일가중 매수 → 평균 fwd_ret - 왕복비용. 벤치마크=동일가중.
- long_short: 상위 top_k 매수 + 하위 top_k 매도(시장중립). 수익=상단평균-하단평균,
  비용은 양쪽 다리에 부과(2×). 시장베타가 제거되므로 **0 대비**로 평가해야 한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..evaluation import metrics


def run_backtest(pred_df: pd.DataFrame, horizon: int, top_k: int,
                 cost_bps: float = 25.0, mode: str = "long") -> dict:
    df = pred_df.dropna(subset=["pred", "fwd_ret"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    dates = np.sort(df["date"].unique())

    # h 거래일 간격으로 논오버랩 리밸런싱일 선택
    rebal_dates = dates[::horizon]
    cost = cost_bps / 1e4  # 왕복 거래비용 (비율)
    need = max(2 * top_k, 2) if mode == "long_short" else max(top_k, 2)

    rows = []
    for d in rebal_dates:
        day = df[df["date"] == d]
        if len(day) < need:
            continue
        longs = day.nlargest(top_k, "pred")
        if mode == "long_short":
            shorts = day.nsmallest(top_k, "pred")
            # 양다리 시장중립: 비용은 매수·매도 양쪽에 부과
            strat_ret = longs["fwd_ret"].mean() - shorts["fwd_ret"].mean() - 2 * cost
        else:
            strat_ret = longs["fwd_ret"].mean() - cost
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
