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


def _compute_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """스냅샷 프레임(ticker·disclosed_at·재무계정)에 재무비율/주당지표를 계산.

    flow(revenue/op/net)은 연간 또는 TTM 값이어야 비율이 의미 있다.
    disclosed_at 순으로 정렬 후 성장률(직전 스냅샷 대비)을 계산.
    """
    df = df.dropna(subset=["disclosed_at"]).copy()
    num = ["revenue", "op_income", "net_income", "assets", "equity", "liabilities", "shares"]
    for c in num:
        if c not in df.columns:
            df[c] = np.nan
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    df = df.sort_values(["ticker", "disclosed_at"]).reset_index(drop=True)

    g = df.groupby("ticker")
    df["f_roe"] = df["net_income"] / df["equity"]
    df["f_op_margin"] = df["op_income"] / df["revenue"]
    # 부채총계 결측 시 자산-자본으로 보완(KR=부채총계, US=assets-equity 일관)
    df["f_liab_to_equity"] = df["liabilities"].fillna(df["assets"] - df["equity"]) / df["equity"]
    # 종목별 첫 스냅샷은 직전이 없어 성장률 결측 → 중립값 0으로 임퓨트(표본 절단 방지)
    df["f_rev_growth"] = g["revenue"].pct_change().fillna(0.0)
    df["bps"] = df["equity"] / df["shares"]   # 주당순자산 (가치 팩터는 가격 결합 시)
    df["eps"] = df["net_income"] / df["shares"]
    return df


def load_fundamentals(dirpath: str | Path) -> pd.DataFrame:
    """fundamentals/*.json (연간) → 스냅샷 long 프레임 + 재무 비율/주당지표."""
    rows = []
    for f in sorted(Path(dirpath).glob("*.json")):
        obj = json.loads(Path(f).read_text(encoding="utf-8"))
        shares = obj.get("shares_outstanding")
        for r in obj.get("reports", []):
            rows.append({
                "ticker": obj["stock_code"],
                "disclosed_at": pd.to_datetime(r.get("disclosed_at")),
                "revenue": r.get("revenue"), "op_income": r.get("op_income"),
                "net_income": r.get("net_income"), "assets": r.get("assets"),
                "equity": r.get("equity"), "liabilities": r.get("liabilities"),
                "shares": shares,
            })
    return _compute_ratios(pd.DataFrame(rows))


def _qidx(year: int, q: int) -> int:
    """분기 순번(연속성 판정용). 2024Q1=8096..."""
    return year * 4 + (q - 1)


def load_fundamentals_quarterly(qdir: str | Path,
                                annual_dir: str | Path) -> pd.DataFrame:
    """분기 재무 → TTM(트레일링 4분기) 스냅샷. 갱신빈도 4배의 PIT 시계열.

    - KR: 분기 손익은 누적(YTD) → 단독분기 = 누적 차분, 연간(annual_dir)으로 Q4 보완.
    - US: 분기 손익은 단독 → 그대로. disclosed_at = 분기말+75일.
    - flow는 연속한 4분기 합(TTM), 재무상태(assets/equity/liab)는 분기말 시점값.
    주식수는 연간 파일에서 재사용.
    """
    annual = {}
    for f in sorted(Path(annual_dir).glob("*.json")):
        o = json.loads(Path(f).read_text(encoding="utf-8"))
        annual[o["stock_code"]] = o

    rows = []
    for f in sorted(Path(qdir).glob("*.json")):
        obj = json.loads(Path(f).read_text(encoding="utf-8"))
        t = obj["stock_code"]
        shares = annual.get(t, {}).get("shares_outstanding")
        flows = ("revenue", "op_income", "net_income")

        # (qidx) -> {standalone flows, BS, disclosed_at}
        standalone = {}
        if obj.get("cumulative"):  # KR: 누적 → 단독
            cum = {}  # qidx -> record(dict)
            for q in obj.get("quarters", []):
                p = q["period"]               # "2024Q1"
                y, qn = int(p[:4]), int(p[5])
                cum[_qidx(y, qn)] = q
            # 연간(FY) = Q4 누적
            for r in annual.get(t, {}).get("reports", []):
                y = int(r["fiscal_year"])
                cum[_qidx(y, 4)] = {**r, "period": f"{y}Q4"}
            for qi in sorted(cum):
                rec = cum[qi]
                p = rec["period"]; y, qn = int(p[:4]), int(p[5])
                if qn == 1:
                    sa = {k: rec.get(k) for k in flows}
                else:
                    prev = cum.get(qi - 1)
                    if prev is None:
                        continue
                    sa = {k: (None if rec.get(k) is None or prev.get(k) is None
                              else rec[k] - prev[k]) for k in flows}
                standalone[qi] = {"sa": sa, "rec": rec,
                                  "disclosed_at": rec.get("disclosed_at")}
        else:  # US: 단독
            for q in obj.get("quarters", []):
                d = pd.to_datetime(q["period_end"])
                qi = _qidx(d.year, (d.month - 1) // 3 + 1)
                standalone[qi] = {
                    "sa": {k: q.get(k) for k in flows}, "rec": q,
                    "disclosed_at": (d + pd.Timedelta(days=75)).date().isoformat(),
                }

        # TTM = 연속한 4분기 단독 합. BS·disclosed_at은 해당 분기 값.
        keys = sorted(standalone)
        for i, qi in enumerate(keys):
            if i < 3 or keys[i - 3:i + 1] != [qi - 3, qi - 2, qi - 1, qi]:
                continue  # 연속 4분기 아님 → TTM 불가
            window = [standalone[k]["sa"] for k in keys[i - 3:i + 1]]
            ttm = {}
            for k in flows:
                vals = [w[k] for w in window]
                ttm[k] = None if any(v is None for v in vals) else sum(vals)
            rec = standalone[qi]["rec"]
            assets = rec.get("assets"); eq = rec.get("equity")
            liab = rec.get("liabilities")
            if liab is None and assets is not None and eq is not None:
                liab = assets - eq
            rows.append({
                "ticker": t, "disclosed_at": pd.to_datetime(standalone[qi]["disclosed_at"]),
                "revenue": ttm["revenue"], "op_income": ttm["op_income"],
                "net_income": ttm["net_income"], "assets": assets,
                "equity": eq, "liabilities": liab, "shares": shares,
            })

    return _compute_ratios(pd.DataFrame(rows))


def load_fundamentals_combined(annual_dir: str | Path,
                               qdir: str | Path) -> pd.DataFrame:
    """연간 + 분기TTM 결합 PIT 시계열. 분기 TTM이 있으면 최근 구간을 더 촘촘히 갱신,
    오래된 구간은 연간이 메운다(merge_asof backward가 가장 최근 공시를 선택)."""
    ann = load_fundamentals(annual_dir)
    q = load_fundamentals_quarterly(qdir, annual_dir)
    both = pd.concat([ann, q], ignore_index=True)
    # 같은 종목·같은 공시일 중복 시 분기(TTM) 우선
    both["_src"] = [0] * len(ann) + [1] * len(q)
    both = (both.sort_values(["ticker", "disclosed_at", "_src"])
                .drop_duplicates(["ticker", "disclosed_at"], keep="last")
                .drop(columns="_src").reset_index(drop=True))
    # 성장률은 결합 후 재계산(시계열이 바뀌므로)
    both["f_rev_growth"] = both.groupby("ticker")["revenue"].pct_change().fillna(0.0)
    return both


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
