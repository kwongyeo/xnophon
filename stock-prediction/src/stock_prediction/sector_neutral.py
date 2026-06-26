"""섹터 중립화 — 시장중립(현 베스트)에 섹터 편향 제거를 더해 비교.

풀링→시장중립으로 KR/US 편향을 제거했다. 그러나 업종(섹터) 쏠림은 잔존 — 예: 기술주
동반 강세를 '종목 선택력'으로 오인할 수 있다. 섹터 중립화는 피처에서 (날짜,섹터) 평균을
빼 업종 효과를 제거한다. 신호가 섹터 내부에서도 살아남으면 더 견고한 알파다.

비교(롱숏, 시장별 동수):
  A 시장중립      : (날짜,시장) zscore
  B 섹터+시장중립 : 섹터 중립화(피처) + 시장별 롱숏

실행: sp-sector
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import (cross_sectional_zscore, load_universe_panel, market_of,
                       run_models, sector_neutralize)
from .config import load_config
from .features.fundamental import (FUND_FEATURE_COLUMNS,
                                   add_fundamental_features, load_fundamentals_combined)
from .features.sector import add_sector
from .features.technical import FEATURE_COLUMNS
from .horizon_sweep import add_target_per_ticker

ROOT = Path(__file__).resolve().parents[2]
FUND = ROOT / "data" / "raw" / "fundamentals"
FUND_Q = ROOT / "data" / "raw" / "fundamentals_q"
SECTORS = ROOT / "data" / "raw" / "meta" / "sectors.json"
STOCK = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS
HORIZONS = [20, 60]


def main() -> None:
    cfg = load_config()
    print("=" * 72)
    print("섹터 중립화 — 시장중립(A) vs 섹터+시장중립(B) · 롱숏(시장별 동수)")
    print("=" * 72)

    base = load_universe_panel(HORIZONS[0])
    base["market"] = base["ticker"].map(market_of)
    base = add_sector(base, SECTORS)
    base = add_fundamental_features(base, load_fundamentals_combined(FUND, FUND_Q))

    nsec = base.groupby("sector")["ticker"].nunique().sort_values(ascending=False)
    print(f"섹터 분포(종목수): {nsec.to_dict()}")

    for h in HORIZONS:
        target = f"target_ret_{h}d"
        panel = add_target_per_ticker(base, h)  # market·sector 컬럼 보존됨
        common = panel.dropna(subset=STOCK + [target]).copy()

        a = cross_sectional_zscore(common, STOCK, by=["market"]).dropna(subset=STOCK)
        A = run_models(a, cfg, h, STOCK, prefiltered=True, do_zscore=False,
                       mode="long_short", group_col="market")
        b = sector_neutralize(common, STOCK).dropna(subset=STOCK)
        B = run_models(b, cfg, h, STOCK, prefiltered=True, do_zscore=False,
                       mode="long_short", group_col="market")

        print(f"\n[h={h}일]  {common['date'].nunique()}거래일 · "
              f"{common['ticker'].nunique()}종목 · 폴드 {A['n_folds']} · 롱숏")
        print(f"  {'구성':<16} {'모델':<10} {'RankIC':>8} {'리밸':>5} {'전략수익':>9} {'샤프':>7} {'MDD':>8}")
        print("  " + "-" * 62)
        for tag, out in (("시장중립", A), ("섹터+시장중립", B)):
            for model in ("Ridge", "LightGBM"):
                r = out["results"].get(model)
                if not r or "error" in r:
                    continue
                s = r["strategy"]
                print(f"  {tag:<16} {model:<10} {r['rank_ic']:>8.3f} "
                      f"{r['n_rebalances']:>5} {s['total_return']:>8.1%} "
                      f"{s['sharpe']:>7.2f} {s['mdd']:>7.1%}")

    print("\n해석: 섹터+시장중립이 시장중립과 비슷하거나 더 좋으면 — 신호가 섹터 내부서도")
    print("      유효(업종 쏠림이 아님). 크게 나빠지면 그간 성과에 섹터 베타가 섞였던 것.")


if __name__ == "__main__":
    main()
