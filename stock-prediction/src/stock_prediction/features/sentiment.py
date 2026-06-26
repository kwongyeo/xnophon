"""심리/관심도 피처 (단계4) — Naver DataLab 검색 트렌드 기반 'attention'.

진짜 감성(긍/부정)은 한국어 금융 감성모델이 필요해 본 단계에서는 **관심도(attention)**
프록시를 쓴다: 검색량 급증은 가격 변동성·뉴스 이벤트에 선행/동반하는 경향.

원본: data/raw/sentiment_kr/<code>.json
  {stock_code, keyword, weekly:[{period(주 시작일), ratio(0~100)}]}

★ 누수 방지: 주별 ratio는 그 주가 끝나야 관측 가능 → available_at = 주 시작일 + 7일.
  일별 패널에는 merge_asof(backward)로 "그 시점까지 완료된 가장 최근 주"만 붙인다.
KR 전용(미국은 Naver 미적용) → 미국 종목은 결측.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SENT_FEATURE_COLUMNS = ["s_attention", "s_attention_chg"]


def load_attention(dirpath: str | Path) -> pd.DataFrame:
    """sentiment_kr/*.json → (ticker, available_at, s_attention, s_attention_chg) long."""
    rows = []
    for f in sorted(Path(dirpath).glob("*.json")):
        obj = json.loads(Path(f).read_text(encoding="utf-8"))
        t = obj["stock_code"]
        w = pd.DataFrame(obj.get("weekly", []))
        if w.empty:
            continue
        w = w.sort_values("period")
        w["ratio"] = pd.to_numeric(w["ratio"], errors="coerce")
        # 트레일링 26주 z-score(과거만) + 주간 변화율
        m = w["ratio"].rolling(26, min_periods=6).mean()
        sd = w["ratio"].rolling(26, min_periods=6).std()
        w["s_attention"] = (w["ratio"] - m) / sd.replace(0, np.nan)
        w["s_attention_chg"] = w["ratio"].pct_change()
        w["ticker"] = t
        # 주 종료 후 관측 → 가용 시점 = 주 시작일 + 7일
        w["available_at"] = pd.to_datetime(w["period"]) + pd.Timedelta(days=7)
        rows.append(w[["ticker", "available_at"] + SENT_FEATURE_COLUMNS])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["ticker", "available_at"] + SENT_FEATURE_COLUMNS)


def add_attention_features(prices: pd.DataFrame, attention: pd.DataFrame) -> pd.DataFrame:
    """일별 가격 패널에 관심도 피처를 PIT merge_asof(backward)로 결합."""
    out = []
    for ticker, px in prices.groupby("ticker"):
        px = px.sort_values("date").copy()
        a = attention[attention["ticker"] == ticker].sort_values("available_at")
        if a.empty:
            for c in SENT_FEATURE_COLUMNS:
                px[c] = np.nan
            out.append(px)
            continue
        merged = pd.merge_asof(px, a.drop(columns="ticker"), left_on="date",
                               right_on="available_at", direction="backward")
        out.append(merged.drop(columns=["available_at"]))
    return pd.concat(out, ignore_index=True)


# 하위호환 별칭
add_sentiment_features = add_attention_features
