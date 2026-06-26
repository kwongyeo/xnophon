"""최종 구성 ablation — 개선들을 누적해 롱숏 성과가 어떻게 좋아지는지 측정.

사다리(h=20, LightGBM 롱숏, 동일 공통 샘플):
  C0 원조      : 풀링 zscore + 연간 펀더멘털
  C1 +분기     : 풀링 zscore + 분기결합 펀더멘털
  C2 +시장중립 : (날짜,시장) zscore + 시장별 동수 롱숏
  C3 +레짐필터 : C2 + 트레일링 VIX 중앙값 미만일 때만 베팅(고VIX 현금)

각 단계가 직전 대비 샤프/MDD를 개선하면 그 개선의 기여로 본다.
실행: sp-final
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import (cross_sectional_zscore, load_universe_panel, market_of,
                       run_models)
from .config import load_config
from .evaluation import metrics
from .features.fundamental import (FUND_FEATURE_COLUMNS, add_fundamental_features,
                                   load_fundamentals, load_fundamentals_combined)
from .features.macro import build_macro_features
from .features.technical import FEATURE_COLUMNS
from .horizon_sweep import add_target_per_ticker

ROOT = Path(__file__).resolve().parents[2]
FUND = ROOT / "data" / "raw" / "fundamentals"
FUND_Q = ROOT / "data" / "raw" / "fundamentals_q"
MACRO = ROOT / "data" / "raw" / "macro"
PROCESSED = ROOT / "data" / "processed"
H = 20
STOCK = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS


def _restrict(d, keys):
    m = [(t, dt) in keys for t, dt in zip(d["ticker"], d["date"])]
    return d[pd.Series(m, index=d.index)].copy()


def _perf(ret, ppy):
    ret = pd.Series(ret).fillna(0.0)
    eq = (1 + ret).cumprod()
    return {"total": float(eq.iloc[-1] - 1), "sharpe": metrics.sharpe_ratio(ret, ppy),
            "mdd": metrics.max_drawdown(eq), "active": float((ret != 0).mean())}


def _regime_filter(curve):
    macro = build_macro_features(MACRO)[["date", "vix_raw"]].sort_values("date").copy()
    macro["trail_med"] = macro["vix_raw"].rolling(252, min_periods=60).median()
    c = pd.merge_asof(curve.sort_values("date"), macro, on="date", direction="backward")
    return c["strat_ret"].where(c["vix_raw"] < c["trail_med"], 0.0)


def main() -> None:
    cfg = load_config()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ppy = 252 / H
    target = f"target_ret_{H}d"

    base = load_universe_panel(H)
    base["market"] = base["ticker"].map(market_of)
    base = add_target_per_ticker(base, H)
    base["market"] = base["ticker"].map(market_of)

    pa = add_fundamental_features(base, load_fundamentals(FUND))
    pq = add_fundamental_features(base, load_fundamentals_combined(FUND, FUND_Q))
    da = pa.dropna(subset=STOCK + [target])
    dq = pq.dropna(subset=STOCK + [target])
    keys = set(zip(da["ticker"], da["date"])) & set(zip(dq["ticker"], dq["date"]))
    da, dq = _restrict(da, keys), _restrict(dq, keys)
    for d in (da, dq):
        d["market"] = d["ticker"].map(market_of)

    print("=" * 70)
    print("최종 구성 ablation — 분기 + 시장중립 + 레짐필터 (h=20, LightGBM 롱숏)")
    print("=" * 70)
    print(f"공통 샘플 {len(da):,}행 · {da['date'].nunique()}거래일 · "
          f"{da['ticker'].nunique()}종목\n")

    def lgb(out):
        return out["results"]["LightGBM"]

    # C0: 풀링 + 연간
    a0 = cross_sectional_zscore(da, STOCK).dropna(subset=STOCK)
    c0 = lgb(run_models(a0, cfg, H, STOCK, prefiltered=True, do_zscore=False,
                        mode="long_short"))
    # C1: 풀링 + 분기
    a1 = cross_sectional_zscore(dq, STOCK).dropna(subset=STOCK)
    c1 = lgb(run_models(a1, cfg, H, STOCK, prefiltered=True, do_zscore=False,
                        mode="long_short"))
    # C2: 시장중립 + 분기
    a2 = cross_sectional_zscore(dq, STOCK, by=["market"]).dropna(subset=STOCK)
    c2 = lgb(run_models(a2, cfg, H, STOCK, prefiltered=True, do_zscore=False,
                        mode="long_short", group_col="market"))
    # C3: C2 + 레짐필터
    c3_ret = _regime_filter(c2["curve"])

    rows = [
        ("C0 원조(풀링+연간)", _perf(c0["curve"]["strat_ret"], ppy)),
        ("C1 +분기펀더", _perf(c1["curve"]["strat_ret"], ppy)),
        ("C2 +시장중립", _perf(c2["curve"]["strat_ret"], ppy)),
        ("C3 +레짐필터(최종)", _perf(c3_ret, ppy)),
    ]
    print(f"  {'구성':<22} {'활성%':>6} {'전략수익':>9} {'샤프':>7} {'MDD':>8}")
    print("  " + "-" * 54)
    for name, p in rows:
        print(f"  {name:<22} {p['active']:>5.0%} {p['total']:>8.1%} "
              f"{p['sharpe']:>7.2f} {p['mdd']:>7.1%}")

    pd.DataFrame([{"config": n, **p} for n, p in rows]).to_parquet(
        PROCESSED / "capstone.parquet", index=False)
    print(f"\n저장 → {PROCESSED}/capstone.parquet")
    print("\n해석: C0→C3로 샤프가 오르고 MDD가 줄면 개선들이 누적 기여한 것.")
    print("주의: 표본 작음(리밸 ~19, C3 활성은 절반). 방향성 지표로 해석.")


if __name__ == "__main__":
    main()
