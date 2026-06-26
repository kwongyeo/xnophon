"""펀더멘털 피처 (단계2).

수익성/안정성/성장성 + 가치(value) 팩터를 구성한다.
재무는 **point-in-time** — 공시 접수일(disclosed_at) 이전 시점에는 사용하지 않는다.
일별 가격 패널에 merge_asof(backward)로 "그 시점까지 가장 최근에 공시된" 재무만 붙인다.

입력 재무 스냅샷(연 1회): data/raw/fundamentals/<code>.json
  {stock_code, name, corp_code, shares_outstanding, reports:[{fiscal_year, disclosed_at,
   revenue, op_income, net_income, assets, liabilities, equity}, ...]}
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# 가격 불필요(재무만) 팩터 + 가격 결합 가치 팩터
FUND_FEATURE_COLUMNS = [
    "f_roe", "f_op_margin", "f_liab_to_equity",
    "f_rev_growth", "f_book_to_price", "f_earnings_yield",
]


def load_fundamentals(dirpath: str | Path) -> pd.DataFrame:
    """fundamentals/*.json → 스냅샷 long 프레임 + 재무 기반 비율/주당지표."""
    rows = []
    for f in sorted(Path(dirpath).glob("*.json")):
        obj = json.loads(Path(f).read_text(encoding="utf-8"))
        shares = obj.get("shares_outstanding")
        for r in obj.get("reports", []):
            rows.append({
                "ticker": obj["stock_code"],
                "fiscal_year": r.get("fiscal_year"),
                "disclosed_at": pd.to_datetime(r.get("disclosed_at")),
                "revenue": r.get("revenue"),
                "op_income": r.get("op_income"),
                "net_income": r.get("net_income"),
                "assets": r.get("assets"),
                "equity": r.get("equity"),
                "liabilities": r.get("liabilities"),
                "shares": shares,
            })
    df = pd.DataFrame(rows).dropna(subset=["disclosed_at"])
    df = df.sort_values(["ticker", "fiscal_year"]).reset_index(drop=True)

    num = ["revenue", "op_income", "net_income", "assets", "equity", "liabilities", "shares"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")

    g = df.groupby("ticker")
    df["f_roe"] = df["net_income"] / df["equity"]
    df["f_op_margin"] = df["op_income"] / df["revenue"]
    # 부채총계가 없으면 자산-자본으로 보완(KR=부채총계, US=assets-equity 일관화)
    df["f_liab_to_equity"] = df["liabilities"].fillna(df["assets"] - df["equity"]) / df["equity"] \
        if "assets" in df.columns else df["liabilities"] / df["equity"]
    # 종목별 첫 회계연도는 직전년이 없어 성장률 결측 → 중립값 0으로 임퓨트(표본 절단 방지)
    df["f_rev_growth"] = g["revenue"].pct_change().fillna(0.0)
    # 주당 지표(가치 팩터는 가격과 결합 시 계산) — 주식수 없으면 NaN
    df["bps"] = df["equity"] / df["shares"]
    df["eps"] = df["net_income"] / df["shares"]
    return df


def add_fundamental_features(prices: pd.DataFrame,
                            snapshots: pd.DataFrame) -> pd.DataFrame:
    """일별 가격 패널에 PIT 재무를 merge_asof(backward)로 결합하고 가치 팩터를 계산.

    prices: 종목별 schema.PRICE 기반 + 기술적 피처(date, ticker, adj_close ...).
    """
    out = []
    snap_cols = ["disclosed_at", "f_roe", "f_op_margin", "f_liab_to_equity",
                 "f_rev_growth", "bps", "eps"]
    for ticker, px in prices.groupby("ticker"):
        px = px.sort_values("date").copy()
        snap = snapshots[snapshots["ticker"] == ticker].sort_values("disclosed_at")
        if snap.empty:
            for c in FUND_FEATURE_COLUMNS:
                px[c] = np.nan
            out.append(px)
            continue
        merged = pd.merge_asof(
            px, snap[snap_cols], left_on="date", right_on="disclosed_at",
            direction="backward",
        )
        # 가치 팩터: 주당순자산/주가, 주당순이익/주가 (높을수록 저평가)
        merged["f_book_to_price"] = merged["bps"] / merged["adj_close"]
        merged["f_earnings_yield"] = merged["eps"] / merged["adj_close"]
        out.append(merged.drop(columns=["disclosed_at", "bps", "eps"]))
    return pd.concat(out, ignore_index=True)
