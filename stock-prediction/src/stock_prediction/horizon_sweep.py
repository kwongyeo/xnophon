"""타깃 기간 스윕 — 예측 기간을 5·20·60일로 바꿔가며 가격 vs 가격+펀더멘털 비교.

가설: 펀더멘털·가치 팩터는 단기(5일)보다 중장기(20·60일)에서 더 유효하다.
새 데이터 불필요 — 기존 50종목 패널에서 타깃 기간만 바꿔 동일 프레임으로 평가.

각 horizon h마다 단계2와 동일한 '동일 샘플 공정 비교'(A 가격 vs B 가격+펀더)를 수행.
embargo=h 로 타깃 중첩 누수를 차단(_fit_windows가 자동 처리), 백테스트는 h일마다 리밸런싱.

실행: sp-horizon   (또는  python -m stock_prediction.horizon_sweep)
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import cross_sectional_zscore, load_universe_panel, run_models
from .config import load_config
from .features.fundamental import (FUND_FEATURE_COLUMNS,
                                   add_fundamental_features, load_fundamentals)
from .features.technical import FEATURE_COLUMNS
from .poc import build_target

FUND_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "fundamentals"
PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"
HORIZONS = [5, 20, 60]


def build_base_panel():
    """가격+기술적+펀더멘털 패널(타깃 제외, horizon 무관)을 한 번만 구성."""
    panel = load_universe_panel(HORIZONS[0])  # 딸려오는 target 컬럼은 무시
    snaps = load_fundamentals(FUND_DIR)
    panel = add_fundamental_features(panel, snaps)
    return panel


def add_target_per_ticker(panel: pd.DataFrame, h: int) -> pd.DataFrame:
    """종목별로 미래 h일 타깃 생성(경계 누수 방지)."""
    parts = [build_target(d, h) for _, d in panel.groupby("ticker", sort=False)]
    return pd.concat(parts, ignore_index=True)


def evaluate_horizon(panel: pd.DataFrame, cfg: dict, h: int) -> dict:
    target = f"target_ret_{h}d"
    all_feats = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS
    data = add_target_per_ticker(panel, h)
    common = data.dropna(subset=all_feats + [target]).copy()
    common = cross_sectional_zscore(common, all_feats).dropna(subset=all_feats)
    if common["date"].nunique() < 60:
        return {"h": h, "error": "표본 부족"}

    A = run_models(common, cfg, h, FEATURE_COLUMNS, prefiltered=True, do_zscore=False)
    B = run_models(common, cfg, h, all_feats, prefiltered=True, do_zscore=False)
    return {"h": h, "n_days": common["date"].nunique(),
            "n_tickers": common["ticker"].nunique(), "A": A, "B": B}


def main() -> None:
    cfg = load_config()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    print("=" * 74)
    print("타깃 기간 스윕 — 5/20/60일 · 가격(A) vs 가격+펀더멘털(B) 동일 샘플 비교")
    print("=" * 74)

    panel = build_base_panel()
    rows = []
    for h in HORIZONS:
        r = evaluate_horizon(panel, cfg, h)
        if "error" in r:
            print(f"\n[h={h}] {r['error']}"); continue
        bench = None
        print(f"\n[h={h}일]  공통 {r['n_days']}거래일 · {r['n_tickers']}종목 · "
              f"폴드 {r['A']['n_folds']}")
        print(f"  {'모델/피처':<18} {'IC':>7} {'RankIC':>8} {'전략수익':>8} {'샤프':>7}")
        print("  " + "-" * 52)
        for model in ("Ridge", "LightGBM"):
            for tag, out in (("A", r["A"]), ("B", r["B"])):
                res = out["results"].get(model)
                if not res or "error" in res:
                    continue
                bench = res["benchmark"]
                s = res["strategy"]
                print(f"  {model+' '+tag:<18} {res['ic']:>7.3f} {res['rank_ic']:>8.3f} "
                      f"{s['total_return']:>8.1%} {s['sharpe']:>7.2f}")
                rows.append({"h": h, "model": model, "feat": tag,
                             "ic": res["ic"], "rank_ic": res["rank_ic"],
                             "sharpe": s["sharpe"], "total_return": s["total_return"]})
        if bench:
            print(f"  {'벤치마크':<18} {'':>7} {'':>8} "
                  f"{bench['total_return']:>8.1%} {bench['sharpe']:>7.2f}")
            rows.append({"h": h, "model": "Benchmark", "feat": "-",
                         "ic": None, "rank_ic": None, "sharpe": bench["sharpe"],
                         "total_return": bench["total_return"]})

    # 펀더멘털 기여(B−A) horizon별 요약
    df = pd.DataFrame(rows)
    print("\n[펀더멘털 기여 = B − A]  RankIC·샤프 개선폭")
    print(f"  {'h':>4} {'모델':<10} {'ΔRankIC':>9} {'Δ샤프':>8}")
    print("  " + "-" * 34)
    for h in HORIZONS:
        for model in ("Ridge", "LightGBM"):
            a = df[(df.h == h) & (df.model == model) & (df.feat == "A")]
            b = df[(df.h == h) & (df.model == model) & (df.feat == "B")]
            if a.empty or b.empty:
                continue
            d_ric = b.rank_ic.iloc[0] - a.rank_ic.iloc[0]
            d_shp = b.sharpe.iloc[0] - a.sharpe.iloc[0]
            print(f"  {h:>4} {model:<10} {d_ric:>+9.3f} {d_shp:>+8.2f}")

    if not df.empty:
        df.to_parquet(PROCESSED / "horizon_sweep.parquet", index=False)
        print(f"\n저장 → {PROCESSED}/horizon_sweep.parquet")
    print("\n해석: h가 길수록 ΔRankIC·Δ샤프가 (+)로 커지면 '펀더멘털은 중장기에 유효' 가설 지지.")


if __name__ == "__main__":
    main()
