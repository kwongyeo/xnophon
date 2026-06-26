"""롱-숏(시장중립) 백테스트 — 기간 스윕에서 확인된 펀더멘털 신호를 수익으로 전환.

기간 스윕 결론: 펀더멘털 RankIC 기여가 중장기(20·60일)에서 크다(60일 LightGBM 0.13).
그러나 상위 K '롱온리'는 강세장 동일가중 벤치마크를 못 넘었다 → 시장베타가 가림.
롱-숏(상위 K 매수 + 하위 K 매도)은 시장베타를 제거하므로 **0 대비**로 신호가 직결된다.

가격+펀더멘털(B) 피처로 중장기 horizon에서 롱온리 vs 롱숏을 비교한다.

실행: sp-longshort   (또는  python -m stock_prediction.longshort)
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import cross_sectional_zscore, run_models
from .config import load_config
from .features.fundamental import FUND_FEATURE_COLUMNS
from .features.technical import FEATURE_COLUMNS
from .horizon_sweep import add_target_per_ticker, build_base_panel

PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"
HORIZONS = [20, 60]
MODELS = ("Ridge", "LightGBM")


def main() -> None:
    cfg = load_config()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    all_feats = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS

    print("=" * 72)
    print("롱-숏(시장중립) 백테스트 — 가격+펀더멘털, 중장기 horizon")
    print("롱온리는 0이 아니라 강세장 벤치마크와 싸운다 / 롱숏은 0 대비 평가")
    print("=" * 72)

    panel = build_base_panel()
    rows = []
    for h in HORIZONS:
        target = f"target_ret_{h}d"
        data = add_target_per_ticker(panel, h)
        common = data.dropna(subset=all_feats + [target]).copy()
        common = cross_sectional_zscore(common, all_feats).dropna(subset=all_feats)

        long_o = run_models(common, cfg, h, all_feats, prefiltered=True,
                            do_zscore=False, mode="long")
        long_s = run_models(common, cfg, h, all_feats, prefiltered=True,
                            do_zscore=False, mode="long_short")

        bench = None
        print(f"\n[h={h}일]  {common['date'].nunique()}거래일 · "
              f"{common['ticker'].nunique()}종목 · 폴드 {long_o['n_folds']}")
        print(f"  {'모델':<10} {'구성':<10} {'RankIC':>8} {'리밸':>5} "
              f"{'전략수익':>9} {'샤프':>7} {'MDD':>8} {'적중':>6}")
        print("  " + "-" * 64)
        for model in MODELS:
            for tag, out in (("롱온리", long_o), ("롱숏(중립)", long_s)):
                r = out["results"].get(model)
                if not r or "error" in r:
                    continue
                bench = r["benchmark"]
                s = r["strategy"]
                print(f"  {model:<10} {tag:<10} {r['rank_ic']:>8.3f} "
                      f"{r['n_rebalances']:>5} {s['total_return']:>8.1%} "
                      f"{s['sharpe']:>7.2f} {s['mdd']:>7.1%} {s['hit']:>6.0%}")
                rows.append({"h": h, "model": model, "mode": tag,
                             "rank_ic": r["rank_ic"], "sharpe": s["sharpe"],
                             "total_return": s["total_return"], "mdd": s["mdd"],
                             "hit": s["hit"]})
        if bench:
            print(f"  {'(참고)':<10} {'동일가중':<10} {'':>8} {'':>5} "
                  f"{bench['total_return']:>8.1%} {bench['sharpe']:>7.2f} "
                  f"{bench['mdd']:>7.1%}")

    if rows:
        pd.DataFrame(rows).to_parquet(PROCESSED / "longshort.parquet", index=False)
        print(f"\n저장 → {PROCESSED}/longshort.parquet")
    print("\n해석: 롱숏 샤프가 (+)로 유의하면 — 강세장 베타가 아니라 '신호 자체'가 수익을")
    print("      낸다는 증거. 롱온리보다 롱숏 샤프가 높으면 시장중립이 신호를 더 잘 산다.")


if __name__ == "__main__":
    main()
