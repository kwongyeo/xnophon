"""레짐 필터 전략 — 단계3의 'VIX 국면 의존성'을 실제 전략으로 전환.

발견: 펀더멘털 롱숏은 저VIX(평온)에서 강하고 고VIX(스트레스)에서 무너진다.
가설: 리밸런싱 시점의 VIX가 높으면 베팅을 쉬고(현금), 낮을 때만 롱숏하면 샤프가 오른다.

★ 누수 방지: 임계값은 **미래정보 없이** 정한다.
  - fixed: 고정 절대값(VIX < 20, 통념적 평온/스트레스 경계)
  - trailing: 과거 252일 VIX 중앙값 미만일 때만 활성(시점마다 과거만 사용)
리밸런싱일의 VIX는 그 시점에 이미 관측되므로, "오늘 VIX로 다음 h일 베팅 여부 결정"은 합법.

실행: sp-regime
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import cross_sectional_zscore, load_universe_panel, run_models
from .config import load_config
from .evaluation import metrics
from .features.fundamental import (FUND_FEATURE_COLUMNS,
                                   add_fundamental_features, load_fundamentals_combined)
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


def _perf(ret: pd.Series, ppy: float) -> dict:
    eq = (1 + ret).cumprod()
    return {"total_return": float(eq.iloc[-1] - 1),
            "sharpe": metrics.sharpe_ratio(ret, ppy),
            "mdd": metrics.max_drawdown(eq),
            "hit": float((ret > 0).mean()), "active": float((ret != 0).mean())}


def main() -> None:
    cfg = load_config()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ppy = 252 / H
    print("=" * 72)
    print("레짐 필터 전략 — 고VIX 구간 현금화로 펀더멘털 롱숏 샤프 개선 검증")
    print("=" * 72)

    # 패널: 가격+기술적 + 분기결합 펀더멘털, 롱숏 LightGBM OOS 예측
    base = load_universe_panel(H)
    snaps = load_fundamentals_combined(FUND, FUND_Q)
    panel = add_fundamental_features(base, snaps)
    data = panel.dropna(subset=STOCK + [f"target_ret_{H}d"]).copy()
    data = cross_sectional_zscore(data, STOCK).dropna(subset=STOCK)
    res = run_models(data, cfg, H, STOCK, prefiltered=True, do_zscore=False,
                     mode="long_short")
    curve = res["results"]["LightGBM"]["curve"].copy()

    # 리밸런싱일 VIX (그 시점 관측치) 결합
    macro = build_macro_features(MACRO)
    vix = macro[["date", "vix_raw"]].copy()
    vix["vix_trail_med"] = vix["vix_raw"].rolling(252, min_periods=60).median()
    curve = pd.merge_asof(curve.sort_values("date"), vix.sort_values("date"),
                          on="date", direction="backward")

    base_ret = curve["strat_ret"]
    strategies = {
        "필터없음(상시)": base_ret,
        "VIX<20 (고정)": base_ret.where(curve["vix_raw"] < 20, 0.0),
        "VIX<25 (고정)": base_ret.where(curve["vix_raw"] < 25, 0.0),
        "VIX<트레일링중앙값": base_ret.where(
            curve["vix_raw"] < curve["vix_trail_med"], 0.0),
    }

    print(f"\nh={H}일 · 롱숏 LightGBM · 리밸 {len(curve)}회 · "
          f"VIX 범위 {curve['vix_raw'].min():.1f}~{curve['vix_raw'].max():.1f}")
    print(f"\n  {'전략':<22} {'활성%':>6} {'전략수익':>9} {'샤프':>7} {'MDD':>8} {'적중':>6}")
    print("  " + "-" * 60)
    rows = []
    for name, ret in strategies.items():
        p = _perf(ret.fillna(0.0), ppy)
        print(f"  {name:<22} {p['active']:>5.0%} {p['total_return']:>8.1%} "
              f"{p['sharpe']:>7.2f} {p['mdd']:>7.1%} {p['hit']:>6.0%}")
        rows.append({"strategy": name, **p})

    pd.DataFrame(rows).to_parquet(PROCESSED / "regime_strategy.parquet", index=False)
    print(f"\n저장 → {PROCESSED}/regime_strategy.parquet")
    print("\n해석: 필터 적용 후 샤프가 '상시'보다 높고 MDD가 줄면 — 레짐 필터가 유효.")
    print("      활성%가 너무 낮으면(과도한 현금) 표본·기회 손실 trade-off 고려.")
    print("주의: 고정 임계값(20/25)은 사전적이지만 그 자체가 사후 지식일 수 있음.")
    print("      트레일링중앙값은 시점별 과거만 사용 → 누수 위험이 가장 낮음.")


if __name__ == "__main__":
    main()
