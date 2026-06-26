"""단계3 — 분기 펀더멘털(항목2) + 거시 레짐(항목3) 통합 평가.

동일 horizon에서 세 피처셋을 동일 샘플(교집합)·롱숏(시장중립)으로 비교:
  B_ann : 가격 + 펀더멘털(연간)
  B_q   : 가격 + 펀더멘털(분기 TTM 결합)        ← 항목2: 갱신빈도 4배
  B_qm  : 가격 + 펀더멘털(분기) + 거시 레짐       ← 항목3: 거시 상호작용

추가로 거시 레짐 분석: LightGBM B_qm 롱숏 수익을 VIX 고/저 국면으로 나눠 샤프 비교.

실행: sp-stage3
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import cross_sectional_zscore, load_universe_panel, run_models
from .config import load_config
from .features.fundamental import (FUND_FEATURE_COLUMNS, add_fundamental_features,
                                   load_fundamentals, load_fundamentals_combined)
from .features.macro import (MACRO_FEATURE_COLUMNS, add_macro_features,
                             build_macro_features)
from .features.technical import FEATURE_COLUMNS
from .horizon_sweep import add_target_per_ticker

ROOT = Path(__file__).resolve().parents[2]
FUND = ROOT / "data" / "raw" / "fundamentals"
FUND_Q = ROOT / "data" / "raw" / "fundamentals_q"
MACRO = ROOT / "data" / "raw" / "macro"
PROCESSED = ROOT / "data" / "processed"
HORIZONS = [20, 60]
STOCK = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS


def _prep(panel, feats, target):
    """공통 샘플 + 종목피처만 횡단면 z(거시는 이미 시계열 z)."""
    d = panel.dropna(subset=feats + [target]).copy()
    d = cross_sectional_zscore(d, [c for c in feats if c in STOCK]).dropna(
        subset=[c for c in feats if c in STOCK])
    return d


def _common_keys(frames):
    keys = None
    for d in frames:
        k = set(zip(d["ticker"], d["date"]))
        keys = k if keys is None else (keys & k)
    return keys


def evaluate(base, ann_snaps, q_snaps, cfg, h):
    target = f"target_ret_{h}d"
    b = add_target_per_ticker(base, h)
    p_ann = add_fundamental_features(b, ann_snaps)
    p_q = add_fundamental_features(b, q_snaps)
    p_qm = add_macro_features(p_q, MACRO)

    d_ann = _prep(p_ann, STOCK, target)
    d_q = _prep(p_q, STOCK, target)
    d_qm = _prep(p_qm, STOCK + MACRO_FEATURE_COLUMNS, target)

    # 세 변형 동일 행(교집합)으로 공정 비교
    keys = _common_keys([d_ann, d_q, d_qm])
    def restrict(d):
        m = [(t, dt) in keys for t, dt in zip(d["ticker"], d["date"])]
        return d[pd.Series(m, index=d.index)].copy()
    d_ann, d_q, d_qm = restrict(d_ann), restrict(d_q), restrict(d_qm)

    runs = {
        "B_ann (연간)": (d_ann, STOCK),
        "B_q (분기)": (d_q, STOCK),
        "B_qm (분기+거시)": (d_qm, STOCK + MACRO_FEATURE_COLUMNS),
    }
    out = {}
    for name, (data, feats) in runs.items():
        out[name] = run_models(data, cfg, h, feats, prefiltered=True,
                               do_zscore=False, mode="long_short")
    return out, d_qm


def regime_split(ls_curve: pd.DataFrame, h: int) -> dict:
    """롱숏 리밸런싱 수익을 VIX 고/저(중앙값) 국면으로 나눠 샤프 비교."""
    from .evaluation.metrics import sharpe_ratio
    macro = build_macro_features(MACRO)[["date", "vix_raw"]]
    c = pd.merge_asof(ls_curve.sort_values("date"), macro.sort_values("date"),
                      on="date", direction="backward")
    med = c["vix_raw"].median()
    ppy = 252 / h
    hi = c[c["vix_raw"] >= med]["strat_ret"]
    lo = c[c["vix_raw"] < med]["strat_ret"]
    return {"vix_median": float(med),
            "high_vix": {"n": len(hi), "mean": float(hi.mean()),
                         "sharpe": sharpe_ratio(hi, ppy)},
            "low_vix": {"n": len(lo), "mean": float(lo.mean()),
                        "sharpe": sharpe_ratio(lo, ppy)}}


def main() -> None:
    cfg = load_config()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    print("=" * 76)
    print("단계3 — 분기 펀더멘털(항목2) + 거시 레짐(항목3) · 롱숏(시장중립) 비교")
    print("=" * 76)

    base = load_universe_panel(HORIZONS[0])
    ann = load_fundamentals(FUND)
    q = load_fundamentals_combined(FUND, FUND_Q)
    print(f"펀더멘털 스냅샷: 연간 {len(ann)} / 분기결합 {len(q)} "
          f"(종목 {q.ticker.nunique()}) · 거시피처 {MACRO_FEATURE_COLUMNS}")

    for h in HORIZONS:
        out, d_qm = evaluate(base, ann, q, cfg, h)
        any_res = next(iter(out.values()))
        print(f"\n[h={h}일]  공통 {d_qm['date'].nunique()}거래일 · "
              f"{d_qm['ticker'].nunique()}종목 · 폴드 {any_res['n_folds']} · 롱숏")
        print(f"  {'피처셋':<18} {'모델':<9} {'RankIC':>8} {'리밸':>5} "
              f"{'전략수익':>9} {'샤프':>7}")
        print("  " + "-" * 58)
        for name, res in out.items():
            for model in ("Ridge", "LightGBM"):
                r = res["results"].get(model)
                if not r or "error" in r:
                    continue
                s = r["strategy"]
                print(f"  {name:<18} {model:<9} {r['rank_ic']:>8.3f} "
                      f"{r['n_rebalances']:>5} {s['total_return']:>8.1%} "
                      f"{s['sharpe']:>7.2f}")

        # 거시 레짐 분석: h=20, B_qm LightGBM
        if h == 20:
            lgb = out["B_qm (분기+거시)"]["results"].get("LightGBM")
            if lgb and "curve" in lgb:
                rg = regime_split(lgb["curve"], h)
                print(f"\n  [거시 레짐: VIX 중앙값 {rg['vix_median']:.1f} 기준, "
                      f"B_qm LightGBM 롱숏]")
                print(f"    고VIX 국면: n={rg['high_vix']['n']:>2}  "
                      f"평균수익 {rg['high_vix']['mean']:+.2%}  샤프 {rg['high_vix']['sharpe']:.2f}")
                print(f"    저VIX 국면: n={rg['low_vix']['n']:>2}  "
                      f"평균수익 {rg['low_vix']['mean']:+.2%}  샤프 {rg['low_vix']['sharpe']:.2f}")

    print("\n해석:")
    print(" - B_q > B_ann (RankIC/샤프)면 분기 펀더멘털(갱신빈도↑)이 기여.")
    print(" - B_qm > B_q면 거시 레짐 상호작용이 기여(주로 LightGBM).")
    print(" - 레짐 분할에서 고/저 VIX 샤프 차이가 크면 전략이 국면 의존적임을 시사.")


if __name__ == "__main__":
    main()
