"""단계2 펀더멘털 — 가격 피처에 point-in-time 재무 팩터를 더해 단계1 기준선과 비교.

핵심 질문: 펀더멘털(수익성/안정성/성장성/가치)을 추가하면 단계1(가격만, IC≈0)을
이기는가? 공정 비교를 위해 **동일 샘플·동일 워크포워드·동일 모델**로 두 피처셋을 돌린다:
  A) 가격만           = FEATURE_COLUMNS
  B) 가격 + 펀더멘털  = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS

실행: sp-stage2   (또는  python -m stock_prediction.stage2)
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import load_universe_panel, run_models
from .config import load_config
from .features.fundamental import (FUND_FEATURE_COLUMNS,
                                   add_fundamental_features, load_fundamentals)
from .features.technical import FEATURE_COLUMNS

FUND_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "fundamentals"
PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


def build_combined_panel(cfg: dict, horizon: int):
    """가격+기술적 패널에 PIT 펀더멘털 피처를 결합."""
    panel = load_universe_panel(horizon)
    if not FUND_DIR.exists() or not any(FUND_DIR.glob("*.json")):
        raise FileNotFoundError(
            f"펀더멘털 데이터 없음: {FUND_DIR} — DART 수집 필요(README 단계2)."
        )
    snaps = load_fundamentals(FUND_DIR)
    panel = add_fundamental_features(panel, snaps)
    return panel, snaps


def _row(name: str, r: dict) -> str:
    s = r["strategy"]
    return (f"{name:<18} {r['ic']:>7.3f} {r['rank_ic']:>8.3f} "
            f"{s['total_return']:>8.1%} {s['sharpe']:>7.2f} {s['mdd']:>7.1%}")


def main() -> None:
    cfg = load_config()
    h = cfg["target"]["horizon"]
    PROCESSED.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("단계2 펀더멘털 — 가격 vs 가격+펀더멘털 (동일 샘플 공정 비교)")
    print("=" * 72)

    panel, snaps = build_combined_panel(cfg, h)
    target = f"target_ret_{h}d"
    all_feats = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS

    # 공통 샘플: 두 피처셋 모두 결측 없는 행만 (apples-to-apples).
    # 횡단면 표준화를 여기서 한 번만 수행 → A·B가 100% 동일한 행/날짜를 쓰도록 보장
    # (그렇지 않으면 각 run의 zscore 후 dropna가 다른 행을 떨궈 표본이 어긋난다).
    from .baseline import cross_sectional_zscore
    common = panel.dropna(subset=all_feats + [target]).copy()
    common = cross_sectional_zscore(common, all_feats).dropna(subset=all_feats)
    n_fund = snaps["ticker"].nunique()
    print(f"\n펀더멘털 종목: {n_fund} · 공통 샘플 {len(common):,}행 · "
          f"거래일 {common['date'].nunique()}일 · 종목 {common['ticker'].nunique()}")
    print(f"펀더멘털 피처: {FUND_FEATURE_COLUMNS}")
    print(f"타깃: 미래 {h}일 수익률 · 상위 {cfg['backtest']['top_k']}종목 롱, "
          f"비용 {cfg['backtest']['cost_bps']}bp")

    priceonly = run_models(common, cfg, h, feature_cols=FEATURE_COLUMNS,
                           prefiltered=True, do_zscore=False)
    combined = run_models(common, cfg, h, feature_cols=all_feats,
                          prefiltered=True, do_zscore=False)

    bench = None
    for tag, out in [("A) 가격만", priceonly), ("B) 가격+펀더멘털", combined)]:
        print(f"\n[{tag}]  (폴드 {out['n_folds']}, 종목 {out['n_tickers']})")
        print(f"  {'모델':<16} {'IC':>7} {'RankIC':>8} {'전략수익':>8} {'샤프':>7} {'MDD':>8}")
        print("  " + "-" * 56)
        for name, r in out["results"].items():
            if "error" in r:
                print(f"  {name}: {r['error']}"); continue
            bench = r["benchmark"]
            print("  " + _row(name, r))
    if bench:
        print(f"\n  벤치마크(동일가중): 수익 {bench['total_return']:.1%} · "
              f"샤프 {bench['sharpe']:.2f} · MDD {bench['mdd']:.1%}")

    # LightGBM 기준 개선폭 요약
    a = priceonly["results"].get("LightGBM")
    b = combined["results"].get("LightGBM")
    if a and b and "error" not in a and "error" not in b:
        print("\n[LightGBM 개선폭: B − A]")
        print(f"  RankIC: {a['rank_ic']:+.3f} → {b['rank_ic']:+.3f} "
              f"(Δ {b['rank_ic'] - a['rank_ic']:+.3f})")
        print(f"  샤프  : {a['strategy']['sharpe']:.2f} → {b['strategy']['sharpe']:.2f} "
              f"(Δ {b['strategy']['sharpe'] - a['strategy']['sharpe']:+.2f})")
        b["curve"].to_parquet(PROCESSED / "stage2_equity_curve.parquet", index=False)
        print(f"\n저장 → {PROCESSED}/stage2_equity_curve.parquet")

    print("\n해석: B의 RankIC/샤프가 A보다 일관되게 높으면 펀더멘털이 기여한 것.")
    print("개선이 미미하면, 대형주·짧은 표본·연 1회 갱신 한계 때문일 수 있다(문서 참조).")


if __name__ == "__main__":
    main()
