"""현재 시점 모델 랭킹 — 최신 단면에서 2개월(≈40거래일) 예측수익 상위 종목.

⚠️ 연구·교육용 모델 출력. 투자 자문/수익 보장 아님. 백테스트상 모델 스킬은
   약하고(RankIC≈0.05) 표본이 작다 — 본 랭킹은 '모델이 상대적으로 선호하는 종목'일 뿐.

구성: 가장 견고했던 설정(가격+기술적 + 분기 TTM 펀더멘털, 시장중립 zscore, LightGBM).
전체 과거(타깃 관측 가능 구간)로 학습 → 최신 날짜 단면에 예측 → 시장별 상위 5.

실행: sp-picks
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .baseline import cross_sectional_zscore, load_universe_panel, market_of
from .config import load_config
from .features.fundamental import (FUND_FEATURE_COLUMNS,
                                   add_fundamental_features, load_fundamentals_combined)
from .features.technical import FEATURE_COLUMNS
from .horizon_sweep import add_target_per_ticker
from .models.tree import TreeModel

ROOT = Path(__file__).resolve().parents[2]
FUND = ROOT / "data" / "raw" / "fundamentals"
FUND_Q = ROOT / "data" / "raw" / "fundamentals_q"
SENT = ROOT / "data" / "raw" / "sentiment_kr"
STOCK = FEATURE_COLUMNS + FUND_FEATURE_COLUMNS
H = 40   # ≈ 2개월(거래일). CLI 인자로 변경 가능: sp-picks 60
TOPK = 5

# 설명용 원시 팩터(시장 내 백분위로 표시)
RAW_FACTORS = ["f_roe", "f_op_margin", "f_liab_to_equity", "f_rev_growth",
               "f_book_to_price", "f_earnings_yield", "mom_20", "rsi_14", "vol_20"]


def _names() -> dict:
    m = {}
    for f in sorted(SENT.glob("*.json")):
        o = json.loads(f.read_text(encoding="utf-8"))
        m[o["stock_code"]] = o.get("keyword", o["stock_code"])
    return m


def main() -> None:
    import sys
    h = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else H
    months = round(h / 21)
    cfg = load_config()
    names = _names()

    base = load_universe_panel(h)
    base["market"] = base["ticker"].map(market_of)
    base = add_fundamental_features(base, load_fundamentals_combined(FUND, FUND_Q))
    panel = add_target_per_ticker(base, h)
    target = f"target_ret_{h}d"

    # 원시 팩터 보존본(설명용) + 모델 입력용 시장중립 zscore본
    raw = panel.copy()
    z = cross_sectional_zscore(panel, STOCK, by=["market"])

    feat_ok = z.dropna(subset=STOCK)
    train = feat_ok.dropna(subset=[target])          # 타깃 관측 가능 = 과거
    model = TreeModel(cfg["model"]["params"], seed=cfg["model"]["seed"]).fit(
        train[STOCK].to_numpy(), train[target].to_numpy())

    # 시장별 최신 거래일 단면에 예측(KR/US 캘린더가 달라 시장별로 따로)
    parts = []
    latest_by_mkt = {}
    for mk in ("KR", "US"):
        sub = feat_ok[feat_ok["market"] == mk]
        if sub.empty:
            continue
        d = sub["date"].max()
        latest_by_mkt[mk] = d
        rows = sub[sub["date"] == d].copy()
        rows["pred"] = model.predict(rows[STOCK].to_numpy())
        parts.append(rows)
    pred_rows = pd.concat(parts, ignore_index=True)

    print("=" * 72)
    print(f"주탐주예 모델 랭킹 — 최신 단면 기준 {h}거래일(≈{months}개월) 예측수익 상위")
    print("⚠️ 연구·교육용. 투자자문/수익보장 아님. 모델 스킬 약함(백테스트 RankIC≈0.05).")
    print("=" * 72)

    # 시장 내 팩터 백분위(설명용)
    for mk, label in (("KR", "한국"), ("US", "미국")):
        d = latest_by_mkt.get(mk)
        sub = raw[(raw["market"] == mk) & (raw["date"] == d)].copy()
        print(f"\n[{label} 상위 {TOPK}]  기준일 {pd.Timestamp(d).date()}"
              f"  (예측수익은 모델 점수 — 실제 보장 아님)")
        ranks = {c: sub[c].rank(pct=True) for c in RAW_FACTORS}
        top = pred_rows[pred_rows["market"] == mk].nlargest(TOPK, "pred")
        for _, r in top.iterrows():
            t = r["ticker"]; nm = names.get(t, t)
            s = sub[sub["ticker"] == t]
            if s.empty:
                continue
            i = s.index[0]
            def pc(c):  # 시장 내 백분위 0~100
                return int(round(ranks[c].loc[i] * 100))
            print(f"  • {t} {nm}  | 예측 {r['pred']:+.1%}")
            print(f"      밸류:  B/P {pc('f_book_to_price')}p, 이익수익률 {pc('f_earnings_yield')}p"
                  f"  | 퀄리티: ROE {pc('f_roe')}p, 영업이익률 {pc('f_op_margin')}p")
            print(f"      성장:  매출성장 {pc('f_rev_growth')}p  | 안전: 부채/자본 {pc('f_liab_to_equity')}p"
                  f"  | 모멘텀 {pc('mom_20')}p, RSI {pc('rsi_14')}p, 변동성 {pc('vol_20')}p")

    print("\n* 백분위(p): 같은 시장 내 상대 순위(100p=최상위). 높을수록 그 팩터가 강함")
    print("  (변동성·부채는 낮을수록 보수적). 모델은 이 팩터들의 비선형 조합으로 점수화.")


if __name__ == "__main__":
    main()
