"""거시·시장 레짐 피처 (단계3).

거시지표(VIX·금리·지수·환율)는 한 날짜에 모든 종목이 동일하므로 **횡단면 zscore로
0이 되어버린다**. 따라서 거시 피처는:
  - 횡단면 표준화하지 않고,
  - 시계열 트레일링 z-score(과거 252일)로 스케일만 맞춰(look-ahead 방지),
  - LightGBM이 '레짐 상호작용'(예: 고VIX일 때 가치 가중↑)으로 쓰도록 한다.
선형(Ridge)에는 날짜 공통 상수라 순위 영향이 없지만, 트리 모델에는 분기 신호를 준다.

원본: data/raw/macro/{SP500,VIX,US10Y,KOSPI,USDKRW,OIL}.json (yfinance 형식)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..data.collectors.yfinance_us import _unwrap

MACRO_FEATURE_COLUMNS = [
    "m_vix", "m_vix_chg5", "m_us10y_chg20", "m_sp_mom20", "m_usdkrw_chg20",
]


def _close_series(path: Path) -> pd.Series:
    recs = _unwrap(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(recs)
    s = pd.Series(df["Close"].astype(float).values,
                  index=pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize())
    return s[~s.index.duplicated(keep="last")].sort_index()


def _tz(s: pd.Series, win: int = 252) -> pd.Series:
    """트레일링 시계열 z-score(과거 win일) — 미래 미사용."""
    m = s.rolling(win, min_periods=60).mean()
    sd = s.rolling(win, min_periods=60).std()
    return (s - m) / sd


def build_macro_features(macro_dir: str | Path) -> pd.DataFrame:
    """거시 원본 → 일별 레짐 피처(date 기준, 시계열 표준화)."""
    d = Path(macro_dir)
    sp = _close_series(d / "SP500.json")
    vix = _close_series(d / "VIX.json")
    us10y = _close_series(d / "US10Y.json")
    usdkrw = _close_series(d / "USDKRW.json")

    # 통합 일자 인덱스로 정렬 + 전진충전(거래일 캘린더 차이 보정)
    idx = sp.index.union(vix.index).union(us10y.index).union(usdkrw.index)
    sp, vix, us10y, usdkrw = (x.reindex(idx).ffill() for x in (sp, vix, us10y, usdkrw))

    feat = pd.DataFrame(index=idx)
    feat["m_vix"] = _tz(vix)                       # 공포 수준(레짐)
    feat["m_vix_chg5"] = vix.pct_change(5)         # 변동성 급변
    feat["m_us10y_chg20"] = us10y.diff(20)         # 금리 추세
    feat["m_sp_mom20"] = sp.pct_change(20)         # 시장 모멘텀
    feat["m_usdkrw_chg20"] = usdkrw.pct_change(20)  # 원화 약세/강세
    feat["vix_raw"] = vix                          # 레짐 분할용(원시 VIX)
    feat.index.name = "date"
    return feat.reset_index()


def add_macro_features(panel: pd.DataFrame, macro_dir: str | Path) -> pd.DataFrame:
    """패널에 거시 피처를 날짜 기준 merge_asof(backward)로 결합(PIT 안전)."""
    macro = build_macro_features(macro_dir).sort_values("date")
    panel = panel.sort_values("date").copy()
    merged = pd.merge_asof(panel, macro, on="date", direction="backward")
    return merged
