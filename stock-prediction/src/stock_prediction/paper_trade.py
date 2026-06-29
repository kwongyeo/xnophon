"""모의투자 추적기 — 모델 추천을 장부(ledger)에 기록하고 실제 수익을 평가.

⚠️ 모의투자(페이퍼 트레이딩) 기록·평가용 연구 도구. 실거래/자문 아님.

사용:
  sp-paper record [horizon] [asof]   # 추천을 장부에 기록(진입가 고정)
  sp-paper report                    # 장부의 모든 포지션을 최신가로 평가
  sp-paper                           # = report

장부: paper_trades/ledger.csv (gitignore 아님 — 기록 보존). 진입 정보만 저장하고,
평가(현재가·수익·청산 여부)는 report 때마다 최신 가격으로 재계산한다.

누수 방지: record 는 rank_asof(asof) 로 'asof 시점에 관측 가능한 데이터만'으로 학습·추천.
실제 운용에서는 매월 한 번 `sp-paper record` 만 돌리면 그날의 추천이 진입가와 함께 쌓인다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .baseline import load_universe_panel, market_of
from .features.macro import _close_series
from .picks import rank_asof

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "paper_trades" / "ledger.csv"
MACRO = ROOT / "data" / "raw" / "macro"

# 시장별 왕복 거래비용(bp). 한국 개인 투자자 기준 현실값(필요시 조정).
#  KR: 매도 증권거래세 ~18bp + 위탁수수료 ~3bp + 슬리피지 ~9bp ≈ 30bp
#  US: 환전 스프레드(원↔달러 왕복) ~100bp + 수수료·슬리피지 ~10bp ≈ 110bp
COST_BPS = {"KR": 30.0, "US": 110.0}

# 시장별 벤치마크 지수 (data/raw/macro)
BENCH_FILE = {"KR": "KOSPI.json", "US": "SP500.json"}

LEDGER_COLS = ["asof_date", "market", "ticker", "name", "horizon",
               "entry_date", "entry_price", "pred"]


def _load_ledger() -> pd.DataFrame:
    if LEDGER.exists():
        return pd.read_csv(LEDGER, dtype={"ticker": str})
    return pd.DataFrame(columns=LEDGER_COLS)


def record(horizon: int, asof) -> None:
    picks = rank_asof(asof=asof, horizon=horizon)
    if picks.empty:
        print("기록할 추천 없음(표본 부족)."); return
    picks["asof_date"] = picks["entry_date"]
    led = _load_ledger()
    combined = pd.concat([led, picks[LEDGER_COLS]], ignore_index=True)
    # 같은 진입일·종목·horizon 중복 제거
    combined = combined.drop_duplicates(["entry_date", "ticker", "horizon"], keep="first")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(LEDGER, index=False)
    print(f"기록 완료: {len(picks)}건 추가 (장부 총 {len(combined)}건) → {LEDGER}")
    for _, r in picks.iterrows():
        print(f"  [{r['market']}] {r['ticker']} {r['name']}  진입 {r['entry_date']} "
              f"@ {r['entry_price']:,.2f}  (h={r['horizon']})")


def _price_lookups():
    """종목별 (date→adj_close) + 시장별 거래일 인덱스 + 벤치마크 지수 시계열."""
    px = load_universe_panel(20)[["date", "ticker", "adj_close"]].copy()
    px["market"] = px["ticker"].map(market_of)
    series = {t: g.set_index("date")["adj_close"].sort_index().dropna()
              for t, g in px.groupby("ticker")}
    mdates = {mk: np.sort(g["date"].unique()) for mk, g in px.groupby("market")}
    bench = {}
    for mk, fn in BENCH_FILE.items():
        f = MACRO / fn
        if f.exists():
            bench[mk] = _close_series(f).dropna()
    return series, mdates, bench


def _asof_price(s: pd.Series, d: pd.Timestamp):
    """d 이하 가장 최근 체결가(없으면 None)."""
    a = s[s.index <= d]
    return float(a.iloc[-1]) if not a.empty else None


def report() -> None:
    led = _load_ledger()
    if led.empty:
        print("장부가 비어 있음. 먼저 'sp-paper record' 로 추천을 기록하세요."); return
    series, mdates, bench = _price_lookups()

    rows = []
    for _, r in led.iterrows():
        t = r["ticker"]; mk = r["market"]; h = int(r["horizon"])
        entry_d = pd.Timestamp(r["entry_date"])
        s = series.get(t)
        if s is None or s.empty:
            continue
        md = mdates.get(mk, np.array([]))
        pos = np.searchsorted(md, np.datetime64(entry_d))
        exit_idx = pos + h                          # 진입 후 h 거래일 = 계획 청산일
        if exit_idx < len(md):
            exit_d = pd.Timestamp(md[exit_idx]); status = "closed"
        else:
            exit_d = pd.Timestamp(s.index.max()); status = "open"
        exit_price = _asof_price(s, exit_d)
        if exit_price is None:
            continue
        cost = COST_BPS.get(mk, 30.0) / 1e4
        gross = exit_price / float(r["entry_price"]) - 1
        net = gross - cost                           # 시장별 현실 비용 차감

        # 벤치마크(같은 기간 KOSPI/S&P500) 대비 초과수익
        bret, excess = np.nan, np.nan
        bs = bench.get(mk)
        if bs is not None:
            be, bx = _asof_price(bs, entry_d), _asof_price(bs, exit_d)
            if be and bx:
                bret = bx / be - 1
                excess = net - bret
        rows.append({"market": mk, "ticker": t, "name": r["name"],
                     "entry_date": entry_d.date().isoformat(), "status": status,
                     "ret": net, "bench": bret, "excess": excess, "h": h})

    ev = pd.DataFrame(rows)
    if ev.empty:
        print("평가 가능한 포지션 없음(가격 데이터 부족)."); return

    print("=" * 80)
    print("모의투자 평가 — 시장별 현실비용(KR 30bp·US 110bp) 차감 + 벤치마크 대비")
    print("벤치마크: KR=KOSPI, US=S&P500 (같은 보유기간). 연구용, 실거래 아님")
    print("=" * 80)
    print(f"  {'시장':<4} {'종목':<8} {'이름':<13} {'진입일':<11} {'상태':<7} "
          f"{'순수익':>8} {'벤치':>7} {'초과':>8}")
    print("  " + "-" * 72)
    for _, r in ev.sort_values(["status", "excess"], ascending=[True, False]).iterrows():
        b = f"{r['bench']:+.1%}" if pd.notna(r['bench']) else "  n/a"
        x = f"{r['excess']:+.1%}" if pd.notna(r['excess']) else "  n/a"
        print(f"  {r['market']:<4} {r['ticker']:<8} {str(r['name'])[:12]:<13} "
              f"{r['entry_date']:<11} {r['status']:<7} {r['ret']:>+7.1%} {b:>7} {x:>8}")

    def line(label, sub):
        if sub.empty:
            return
        xx = sub["excess"].dropna()
        msg = (f"   - {label:<8} n={len(sub):>2}  순수익 평균 {sub['ret'].mean():+.1%}·"
               f"중앙값 {sub['ret'].median():+.1%}  승률 {(sub['ret'] > 0).mean():.0%}")
        if len(xx):
            msg += f"  |  초과 평균 {xx.mean():+.1%}  벤치초과율 {(xx > 0).mean():.0%}"
        print(msg)

    print("\n  [요약] (초과 = 순수익 − 같은기간 벤치마크)")
    line("전체", ev)
    line("청산완료", ev[ev.status == "closed"])
    line("보유중", ev[ev.status == "open"])
    line("KR", ev[ev.market == "KR"])
    line("US", ev[ev.market == "US"])
    print("\n주의: 모의 성과·미래 보장 아님. 비용은 가정치(KR 거래세+수수료, US 환전 스프레드);")
    print("      벤치마크는 매수비용 미반영(총수익 기준). 슬리피지·체결지연 등 추가 변수 존재.")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "record":
        rest = args[1:]
        horizon = next((int(a) for a in rest if a.isdigit()), 40)
        asof = next((a for a in rest if not a.isdigit()), None)
        record(horizon, asof)
    else:
        report()


if __name__ == "__main__":
    main()
