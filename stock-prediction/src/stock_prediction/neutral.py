"""시장중립화 — 풀링(KR·US 한 단면) vs 시장 내(within-market) 정규화·롱숏 비교.

방법론적 약점: 지금까지는 한국·미국 종목을 같은 날 한 횡단면에서 같이 zscore·롱숏했다
(풀링). 통화·시장 수준·밸류에이션 관행이 달라 편향이 섞인다. 시장중립화는:
  - 피처를 (날짜, 시장)별로 zscore (시장 내 상대화),
  - 롱숏을 시장별로 동수 구성(KR 내 top/bottom + US 내 top/bottom).
신호가 시장 내부에서도 살아남으면 더 견고한 알파다.

실행: sp-neutral  (h=20, 분기결합 펀더멘털, 롱숏)
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import (cross_sectional_zscore, load_universe_panel, market_of,
                       run_models)
from .config import load_config
from .features.fundamental import (FUND_FEATURE_COLUMNS,
                                   add_fundamental_features, load_fundamentals_combined)
from .features.technical import FEATURE_COLUMNS
from .horizon_sweep import add_target_per_ticker

ROOT = Path(__file__).resolve().parents[2]
FUND = ROOT / "data" / "raw" / "fundamentals"
FUND_Q = ROOT / "data" / "raw" / "fundamentals_q"
STOCK = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS
HORIZONS = [20, 60]


def main() -> None:
    cfg = load_config()
    print("=" * 74)
    print("시장중립화 — 풀링 vs 시장 내(within-market) 정규화·롱숏 (한국+미국)")
    print("=" * 74)

    base = load_universe_panel(HORIZONS[0])
    base["market"] = base["ticker"].map(market_of)
    snaps = load_fundamentals_combined(FUND, FUND_Q)
    panel0 = add_fundamental_features(base, snaps)

    for h in HORIZONS:
        target = f"target_ret_{h}d"
        panel = add_target_per_ticker(panel0, h)
        if "market" not in panel.columns:
            panel["market"] = panel["ticker"].map(market_of)
        common = panel.dropna(subset=STOCK + [target]).copy()

        # A) 풀링: 날짜별 zscore + 풀링 롱숏
        a = cross_sectional_zscore(common, STOCK).dropna(subset=STOCK)
        pooled = run_models(a, cfg, h, STOCK, prefiltered=True, do_zscore=False,
                            mode="long_short")
        # B) 시장중립: (날짜,시장)별 zscore + 시장별 동수 롱숏
        b = cross_sectional_zscore(common, STOCK, by=["market"]).dropna(subset=STOCK)
        neutral = run_models(b, cfg, h, STOCK, prefiltered=True, do_zscore=False,
                             mode="long_short", group_col="market")

        n_kr = (common["market"] == "KR").groupby(common["date"]).any().sum()
        print(f"\n[h={h}일]  {common['date'].nunique()}거래일 · "
              f"{common['ticker'].nunique()}종목(KR+US) · 폴드 {pooled['n_folds']} · 롱숏")
        print(f"  {'구성':<16} {'모델':<10} {'RankIC':>8} {'리밸':>5} {'전략수익':>9} {'샤프':>7} {'MDD':>8}")
        print("  " + "-" * 62)
        for tag, out in (("풀링", pooled), ("시장중립", neutral)):
            for model in ("Ridge", "LightGBM"):
                r = out["results"].get(model)
                if not r or "error" in r:
                    continue
                s = r["strategy"]
                print(f"  {tag:<16} {model:<10} {r['rank_ic']:>8.3f} "
                      f"{r['n_rebalances']:>5} {s['total_return']:>8.1%} "
                      f"{s['sharpe']:>7.2f} {s['mdd']:>7.1%}")

    print("\n해석: 시장중립의 샤프/MDD가 풀링과 비슷하거나 더 좋으면 — 신호가 시장 내부에서도")
    print("      유효(풀링이 KR/US 수준차에 기댄 게 아님). 크게 나빠지면 풀링 효과가 컸던 것.")


if __name__ == "__main__":
    main()
