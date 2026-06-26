"""단계4 — 뉴스/검색 관심도(attention) 피처 효과 검증.

Naver DataLab 검색 트렌드(관심도)를 가격+펀더멘털에 더해 단기 신호가 개선되는지 검증.
Naver는 KR 전용이므로 미국 종목 관심도는 중립값 0으로 채워, **신호가 작동하는 결합
유니버스(KR+US, 시장중립 롱숏)** 위에서 관심도 기여만 분리 평가한다.
(참고: KR 단독 21종목 롱숏은 베이스 자체가 음(-)이라 관심도 효과 분리가 무의미.)

A: 가격 + 펀더멘털
B: 가격 + 펀더멘털 + 관심도(attention; US=0 중립)
동일 샘플·시장중립 롱숏. 관심도는 단기 이벤트에 민감 → 짧은 horizon에서 효과 기대.

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
    base["market"] = base["ticker"].map(market_of)    # 결합 유니버스(KR+US)
    base = add_fundamental_features(base, load_fundamentals_combined(FUND, FUND_Q))
    base = add_attention_features(base, load_attention(SENT))
    # 미국 종목 관심도(Naver 미적용)는 중립값 0으로 채움 → 결합 유니버스 유지
    for c in SENT_FEATURE_COLUMNS:
        base[c] = base[c].fillna(0.0)

    allf = STOCK + SENT_FEATURE_COLUMNS
    for h in HORIZONS:
        target = f"target_ret_{h}d"
        panel = add_target_per_ticker(base, h)
        common = panel.dropna(subset=STOCK + [target]).copy()
        if common["date"].nunique() < 80:
            print(f"\n[h={h}] 표본 부족({common['date'].nunique()}일)"); continue
        # 종목 피처는 (날짜,시장) zscore(시장중립), 관심도는 결합 단면 zscore
        z = cross_sectional_zscore(common, STOCK, by=["market"])
        z = cross_sectional_zscore(z, SENT_FEATURE_COLUMNS).dropna(subset=STOCK)
        z[SENT_FEATURE_COLUMNS] = z[SENT_FEATURE_COLUMNS].fillna(0.0)  # 워밍업 NaN 중립화

        A = run_models(z, cfg, h, STOCK, prefiltered=True, do_zscore=False,
                       mode="long_short", group_col="market")
        B = run_models(z, cfg, h, allf, prefiltered=True, do_zscore=False,
                       mode="long_short", group_col="market")

        print(f"\n[h={h}일]  {z['date'].nunique()}거래일 · {z['ticker'].nunique()}종목(KR+US) · "
              f"폴드 {A['n_folds']} · 시장중립 롱숏")
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

    print("\n해석: B의 RankIC/샤프가 A보다 높으면 관심도가 기여. 관심도는 진짜 감성(긍/부정)이")
    print("      아닌 검색량 프록시 — 방향성 없는 노이즈일 수 있음(KR만 변동, US=0 중립).")


if __name__ == "__main__":
    main()
