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
from .picks import rank_asof

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "paper_trades" / "ledger.csv"
COST_BPS = 25.0  # 왕복 거래비용 가정(평가에 반영)

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
    """종목별 (date→adj_close) + 시장별 거래일 인덱스."""
    px = load_universe_panel(20)[["date", "ticker", "adj_close"]].copy()
    px["market"] = px["ticker"].map(market_of)
    series = {t: g.set_index("date")["adj_close"].sort_index().dropna()
              for t, g in px.groupby("ticker")}
    mdates = {mk: np.sort(g["date"].unique()) for mk, g in px.groupby("market")}
    return series, mdates


def report() -> None:
    led = _load_ledger()
    if led.empty:
        print("장부가 비어 있음. 먼저 'sp-paper record' 로 추천을 기록하세요."); return
    series, mdates = _price_lookups()
    cost = COST_BPS / 1e4

    rows = []
    for _, r in led.iterrows():
        t = r["ticker"]; mk = r["market"]; h = int(r["horizon"])
        entry_d = pd.Timestamp(r["entry_date"])
        s = series.get(t)
        if s is None or s.empty:
            continue
        md = mdates.get(mk, np.array([]))
        # 계획 청산일 = 진입 후 h 거래일
        pos = np.searchsorted(md, np.datetime64(entry_d))
        exit_idx = pos + h
        last_d = pd.Timestamp(s.index.max())
        if exit_idx < len(md):                      # 청산 완료
            exit_d = pd.Timestamp(md[exit_idx]); status = "closed"
        else:                                        # 보유 중 → 현재가 평가
            exit_d = last_d; status = "open"
        # 평가가 = exit_d 이하 가장 최근 체결가
        avail = s[s.index <= exit_d]
        if avail.empty:
            continue
        exit_price = float(avail.iloc[-1])
        gross = exit_price / float(r["entry_price"]) - 1
        net = gross - cost                           # 왕복비용 차감
        rows.append({"market": mk, "ticker": t, "name": r["name"],
                     "entry_date": entry_d.date().isoformat(),
                     "entry": float(r["entry_price"]), "evalp": exit_price,
                     "status": status, "ret": net, "h": h})

    ev = pd.DataFrame(rows)
    if ev.empty:
        print("평가 가능한 포지션 없음(가격 데이터 부족)."); return

    print("=" * 76)
    print("모의투자 평가 (왕복비용 25bp 차감) — 연구용, 실거래 아님")
    print("=" * 76)
    print(f"  {'시장':<4} {'종목':<8} {'이름':<14} {'진입일':<11} {'상태':<7} "
          f"{'진입가':>10} {'평가가':>10} {'수익률':>8}")
    print("  " + "-" * 74)
    for _, r in ev.sort_values(["status", "ret"], ascending=[True, False]).iterrows():
        print(f"  {r['market']:<4} {r['ticker']:<8} {str(r['name'])[:13]:<14} "
              f"{r['entry_date']:<11} {r['status']:<7} {r['entry']:>10,.2f} "
              f"{r['evalp']:>10,.2f} {r['ret']:>+7.1%}")

    print("\n  [요약]")
    for label, sub in [("전체", ev), ("청산완료", ev[ev.status == "closed"]),
                       ("보유중", ev[ev.status == "open"])]:
        if sub.empty:
            continue
        print(f"   - {label:<6} n={len(sub):>2}  평균 {sub['ret'].mean():+.1%}  "
              f"중앙값 {sub['ret'].median():+.1%}  승률 {(sub['ret'] > 0).mean():.0%}  "
              f"최고 {sub['ret'].max():+.1%}  최저 {sub['ret'].min():+.1%}")
    for mk in ("KR", "US"):
        sub = ev[ev.market == mk]
        if not sub.empty:
            print(f"   - {mk:<6} n={len(sub):>2}  평균 {sub['ret'].mean():+.1%}  "
                  f"승률 {(sub['ret'] > 0).mean():.0%}")
    print("\n주의: 모델 추천의 모의 성과일 뿐, 미래 보장 아님. 슬리피지·세금·체결지연 미반영.")


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
