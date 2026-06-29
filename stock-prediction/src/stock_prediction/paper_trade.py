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

# 현지통화 기준 왕복 비용(bp). US는 환율을 별도 모델링하므로 FX 레벨변동은 비용이 아님.
#  KR: 매도 거래세 ~18 + 수수료 ~3 + 슬리피지 ~9 ≈ 30bp
#  US: 위탁수수료·슬리피지 ~10bp (환전 스프레드는 KRW 비용에 별도 반영)
COST_BPS = {"KR": 30.0, "US": 10.0}
# 원화 기준 왕복 비용(bp): KR 동일, US는 환전 스프레드(~50) + 수수료(~10) = 60
KRW_COST_BPS = {"KR": 30.0, "US": 60.0}

# 시장별 벤치마크 지수 (data/raw/macro)
BENCH_FILE = {"KR": "KOSPI.json", "US": "SP500.json"}
FX_FILE = "USDKRW.json"   # 원/달러 (US 포지션 원화 환산)

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


def _lookups():
    """종목별 KRW·현지가 시계열, 시장 거래일, 벤치마크(KRW), 환율."""
    px = load_universe_panel(20)[["date", "ticker", "adj_close"]].copy()
    px["market"] = px["ticker"].map(market_of)
    local = {t: g.set_index("date")["adj_close"].sort_index().dropna()
             for t, g in px.groupby("ticker")}
    mdates = {mk: np.sort(g["date"].unique()) for mk, g in px.groupby("market")}
    fx = _close_series(MACRO / FX_FILE).dropna() if (MACRO / FX_FILE).exists() else None

    def to_krw(t, mk):
        s = local[t]
        if mk == "KR" or fx is None:
            return s
        f = fx.reindex(s.index).ffill().bfill()     # 원/달러를 종목 일자에 정렬
        return (s * f).dropna()

    krw = {t: to_krw(t, market_of(t)) for t in local}
    bench = {}
    for mk, fn in BENCH_FILE.items():
        f = MACRO / fn
        if not f.exists():
            continue
        b = _close_series(f).dropna()
        if mk == "US" and fx is not None:           # S&P500도 원화 환산
            b = (b * fx.reindex(b.index).ffill().bfill()).dropna()
        bench[mk] = b
    return local, krw, mdates, bench, fx


def _asof(s, d):
    a = s[s.index <= d]
    return float(a.iloc[-1]) if not a.empty else None


def _exit_with_stop(s_krw, entry_krw, entry_d, planned_exit_d, stop):
    """보유기간 중 종가가 진입가×(1−stop) 이하로 내려가면 그날 청산(손절).
    반환: (exit_date, exit_price_krw, stopped?)"""
    if not stop:
        return planned_exit_d, _asof(s_krw, planned_exit_d), False
    win = s_krw[(s_krw.index > entry_d) & (s_krw.index <= planned_exit_d)]
    lvl = entry_krw * (1 - stop)
    breach = win[win <= lvl]
    if not breach.empty:
        d0 = breach.index[0]
        return pd.Timestamp(d0), float(breach.iloc[0]), True
    return planned_exit_d, _asof(s_krw, planned_exit_d), False


def _evaluate(led, stop=0.0):
    """장부 → 포지션별 평가(원화 기준). 손절(stop) 옵션 반영."""
    local, krw, mdates, bench, fx = _lookups()
    rows = []
    for _, r in led.iterrows():
        t, mk, h = r["ticker"], r["market"], int(r["horizon"])
        entry_d = pd.Timestamp(r["entry_date"])
        sL, sK = local.get(t), krw.get(t)
        if sK is None or sK.empty:
            continue
        md = mdates.get(mk, np.array([]))
        pos = np.searchsorted(md, np.datetime64(entry_d))
        exit_idx = pos + h
        if exit_idx < len(md):
            planned_exit, status = pd.Timestamp(md[exit_idx]), "closed"
        else:
            planned_exit, status = pd.Timestamp(sK.index.max()), "open"
        entry_local = float(r["entry_price"])
        entry_krw = _asof(sK, entry_d)
        if entry_krw is None:
            continue
        exit_d, exit_krw, stopped = _exit_with_stop(sK, entry_krw, entry_d, planned_exit, stop)
        if exit_krw is None:
            continue
        if stopped:
            status = "stopped"
        # 원화 순수익 = 환율 반영 - 원화비용
        ret_krw = exit_krw / entry_krw - 1 - KRW_COST_BPS.get(mk, 30) / 1e4
        # 현지통화 순수익(참고)
        exit_local = _asof(sL, exit_d)
        ret_local = (exit_local / entry_local - 1 - COST_BPS.get(mk, 30) / 1e4
                     if exit_local else np.nan)
        # 벤치마크(원화) 대비 초과
        bret = excess = np.nan
        bs = bench.get(mk)
        if bs is not None:
            be, bx = _asof(bs, entry_d), _asof(bs, exit_d)
            if be and bx:
                bret = bx / be - 1
                excess = ret_krw - bret
        rows.append({"market": mk, "ticker": t, "name": r["name"],
                     "entry_date": entry_d.date().isoformat(),
                     "exit_date": pd.Timestamp(exit_d).date().isoformat(),
                     "status": status, "ret_krw": ret_krw, "ret_local": ret_local,
                     "bench": bret, "excess": excess})
    return pd.DataFrame(rows)


def _daily_nav(led, stop=0.0):
    """일별 포트폴리오 NAV(원화, 활성 포지션 동일가중) + 벤치마크 NAV."""
    local, krw, mdates, bench, fx = _lookups()
    day_pos, day_bench = {}, {}
    for _, r in led.iterrows():
        t, mk, h = r["ticker"], r["market"], int(r["horizon"])
        entry_d = pd.Timestamp(r["entry_date"])
        sK = krw.get(t)
        if sK is None or sK.empty:
            continue
        md = mdates.get(mk, np.array([]))
        pos = np.searchsorted(md, np.datetime64(entry_d))
        planned_exit = pd.Timestamp(md[min(pos + h, len(md) - 1)])
        entry_krw = _asof(sK, entry_d)
        exit_d, _, _ = _exit_with_stop(sK, entry_krw, entry_d, planned_exit, stop)
        path = sK[(sK.index > entry_d) & (sK.index <= exit_d)]
        if path.empty:
            continue
        rets = path.pct_change()
        rets.iloc[0] = path.iloc[0] / entry_krw - 1 - KRW_COST_BPS.get(mk, 30) / 1e4
        for d, x in rets.items():
            day_pos.setdefault(pd.Timestamp(d), []).append(float(x))
        # 같은 기간 벤치마크 일별수익(시장 노출 매칭용)
        bs = bench.get(mk)
        if bs is not None:
            bpath = bs[(bs.index > entry_d) & (bs.index <= exit_d)].pct_change().dropna()
            for d, x in bpath.items():
                day_bench.setdefault(pd.Timestamp(d), []).append(float(x))
    if not day_pos:
        return None
    idx = sorted(day_pos)
    port = pd.Series({d: np.mean(day_pos[d]) for d in idx}).sort_index()
    nav = (1 + port).cumprod()
    bser = pd.Series({d: np.mean(day_bench[d]) for d in day_bench}).reindex(nav.index).fillna(0)
    bnav = (1 + bser).cumprod()
    return pd.DataFrame({"date": nav.index, "nav": nav.values, "bench_nav": bnav.values})


def _mdd(nav):
    return float((nav / nav.cummax() - 1).min())


def _sparkline(vals):
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return blocks[0] * len(vals)
    step = max(1, len(vals) // 60)
    s = vals[::step]
    return "".join(blocks[min(7, int((v - lo) / (hi - lo) * 7))] for v in s)


def report(stop=0.0) -> None:
    led = _load_ledger()
    if led.empty:
        print("장부가 비어 있음. 먼저 'sp-paper record' 로 추천을 기록하세요."); return
    ev = _evaluate(led, stop=stop)
    if ev.empty:
        print("평가 가능한 포지션 없음(가격 데이터 부족)."); return

    sl = f" · 손절 -{stop:.0%}" if stop else ""
    print("=" * 82)
    print(f"모의투자 평가 (원화 기준, 실제 USD/KRW 반영){sl} — 연구용, 실거래 아님")
    print("비용: KR 30bp / US 60bp(환전 스프레드 포함) · 벤치마크: KOSPI / S&P500(원화)")
    print("=" * 82)
    print(f"  {'시장':<4} {'종목':<8} {'이름':<12} {'진입일':<11} {'상태':<8} "
          f"{'원화순익':>8} {'현지':>7} {'초과':>8}")
    print("  " + "-" * 74)
    for _, r in ev.sort_values(["status", "excess"], ascending=[True, False]).iterrows():
        lc = f"{r['ret_local']:+.1%}" if pd.notna(r['ret_local']) else " n/a"
        x = f"{r['excess']:+.1%}" if pd.notna(r['excess']) else " n/a"
        print(f"  {r['market']:<4} {r['ticker']:<8} {str(r['name'])[:11]:<12} "
              f"{r['entry_date']:<11} {r['status']:<8} {r['ret_krw']:>+7.1%} {lc:>7} {x:>8}")

    def line(label, sub):
        if sub.empty:
            return
        xx = sub["excess"].dropna()
        msg = (f"   - {label:<8} n={len(sub):>2}  원화순익 평균 {sub['ret_krw'].mean():+.1%}·"
               f"중앙값 {sub['ret_krw'].median():+.1%}  승률 {(sub['ret_krw'] > 0).mean():.0%}")
        if len(xx):
            msg += f"  | 초과 {xx.mean():+.1%}  벤치초과율 {(xx > 0).mean():.0%}"
        print(msg)

    print("\n  [요약] (원화 기준, 초과 = 원화순익 − 같은기간 벤치마크(원화))")
    line("전체", ev); line("청산완료", ev[ev.status == "closed"])
    line("보유중", ev[ev.status == "open"]); line("손절", ev[ev.status == "stopped"])
    line("KR", ev[ev.market == "KR"]); line("US", ev[ev.market == "US"])

    # 누적 자산곡선
    curve = _daily_nav(led, stop=stop)
    if curve is not None and len(curve) > 2:
        out_csv = LEDGER.parent / "equity_curve.csv"
        curve.to_csv(out_csv, index=False)
        nav, bnav = curve["nav"].values, curve["bench_nav"].values
        print("\n  [누적 자산곡선] (원화, 활성 포지션 동일가중)")
        print(f"    전략 : {_sparkline(list(nav))}  총 {nav[-1]-1:+.1%} · MDD {_mdd(curve['nav']):.1%}")
        print(f"    벤치 : {_sparkline(list(bnav))}  총 {bnav[-1]-1:+.1%} · MDD {_mdd(curve['bench_nav']):.1%}")
        print(f"    기간 {curve['date'].iloc[0].date()} ~ {curve['date'].iloc[-1].date()}"
              f"  → {out_csv.name}")
        _save_plot(curve)

    print("\n주의: 모의 성과·미래 보장 아님. 비용·환율 스프레드는 가정치. 벤치마크는 매수비용 미반영.")


def _save_plot(curve) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(curve["date"], curve["nav"], label="Strategy (KRW)", lw=2)
    ax.plot(curve["date"], curve["bench_nav"], label="Benchmark (KRW)", lw=1.3, ls="--")
    ax.axhline(1.0, color="gray", lw=0.6)
    ax.set_title("Paper-trade equity curve (KRW, equal-weight active)")
    ax.set_ylabel("NAV (start=1.0)"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    p = LEDGER.parent / "equity_curve.png"
    fig.savefig(p, dpi=110); plt.close(fig)
    print(f"    그래프 저장 → {p.name}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "record":
        rest = args[1:]
        horizon = next((int(a) for a in rest if a.isdigit()), 40)
        asof = next((a for a in rest if not a.isdigit()), None)
        record(horizon, asof)
    else:
        # report [stop%]  예: sp-paper report 15  → 15% 손절 시뮬
        nums = [a for a in args if a.replace(".", "").isdigit()]
        stop = float(nums[0]) / 100 if nums else 0.0
        report(stop=stop)


if __name__ == "__main__":
    main()
