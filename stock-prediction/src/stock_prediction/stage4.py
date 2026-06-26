"""단계4 — 뉴스/검색 관심도(attention) 피처 효과 검증 (한국 단독).

Naver DataLab 검색 트렌드(관심도)를 가격+펀더멘털에 더해 단기 신호가 개선되는지 검증.
Naver는 KR 전용이므로 **한국 종목만**으로 평가(단일 시장 → 풀링 롱숏).

A: 가격 + 펀더멘털
B: 가격 + 펀더멘털 + 관심도(attention)
동일 샘플·롱숏. 관심도는 단기 변동성·이벤트에 민감 → 짧은 horizon에서 효과 기대.

실행: sp-stage4
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import cross_sectional_zscore, load_universe_panel, market_of, run_models
from .config import load_config
from .features.fundamental import (FUND_FEATURE_COLUMNS,
                                   add_fundamental_features, load_fundamentals_combined)
from .features.sentiment import (SENT_FEATURE_COLUMNS, add_attention_features,
                                 load_attention)
from .features.technical import FEATURE_COLUMNS
from .horizon_sweep import add_target_per_ticker

ROOT = Path(__file__).resolve().parents[2]
FUND = ROOT / "data" / "raw" / "fundamentals"
FUND_Q = ROOT / "data" / "raw" / "fundamentals_q"
SENT = ROOT / "data" / "raw" / "sentiment_kr"
STOCK = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS
HORIZONS = [5, 20]


def main() -> None:
    cfg = load_config()
    print("=" * 70)
    print("단계4 — 검색 관심도(attention) 효과 (한국 단독, 롱숏)")
    print("=" * 70)

    base = load_universe_panel(HORIZONS[0])
    base["market"] = base["ticker"].map(market_of)
    base = base[base["market"] == "KR"].copy()        # 한국 종목만
    base = add_fundamental_features(base, load_fundamentals_combined(FUND, FUND_Q))
    base = add_attention_features(base, load_attention(SENT))

    allf = STOCK + SENT_FEATURE_COLUMNS
    for h in HORIZONS:
        target = f"target_ret_{h}d"
        panel = add_target_per_ticker(base, h)
        common = panel.dropna(subset=allf + [target]).copy()
        if common["date"].nunique() < 80:
            print(f"\n[h={h}] 표본 부족({common['date'].nunique()}일)"); continue
        z = cross_sectional_zscore(common, allf).dropna(subset=allf)

        A = run_models(z, cfg, h, STOCK, prefiltered=True, do_zscore=False, mode="long_short")
        B = run_models(z, cfg, h, allf, prefiltered=True, do_zscore=False, mode="long_short")

        print(f"\n[h={h}일]  {z['date'].nunique()}거래일 · {z['ticker'].nunique()}종목(KR) · "
              f"폴드 {A['n_folds']} · 롱숏")
        print(f"  {'피처셋':<14} {'모델':<10} {'RankIC':>8} {'리밸':>5} {'전략수익':>9} {'샤프':>7}")
        print("  " + "-" * 56)
        for tag, out in (("A 가격+펀더", A), ("B +관심도", B)):
            for model in ("Ridge", "LightGBM"):
                r = out["results"].get(model)
                if not r or "error" in r:
                    continue
                s = r["strategy"]
                print(f"  {tag:<14} {model:<10} {r['rank_ic']:>8.3f} "
                      f"{r['n_rebalances']:>5} {s['total_return']:>8.1%} {s['sharpe']:>7.2f}")

    print("\n해석: B의 RankIC/샤프가 A보다 높으면 관심도가 기여. 단 KR 24종목·관심도는")
    print("      진짜 감성이 아닌 검색량 프록시라는 한계.")


if __name__ == "__main__":
    main()
