"""sp-refresh — 로컬에서 데이터 최신화 (yfinance 기반).

⚠️ 이 클라우드 샌드박스는 Yahoo Finance 접속이 차단되어 **실행 불가**.
   반드시 **로컬 PC**(차단 없는 환경)에서 실행할 것. 인터넷 필요.

무엇을 갱신하나 (매일 변하는 데이터가 핵심):
  prices  : 유니버스 50종목 시세(KR `.KS` + US) → data/raw/universe/   ★기본
  macro   : 지수·금리·환율·유가 6종 → data/raw/macro/                 ★기본
  sectors : GICS 섹터 → data/raw/meta/sectors.json
  us-fund : 미국 재무(연간+분기) → data/raw/fundamentals(_q)/

한국 재무(DART)·검색 관심도(Naver)는 분기성이라 자주 갱신 불필요 → 기존 스냅샷 유지.
필요 시 API 키로 별도 수집(README/.env.example 참조).

사용:
  sp-refresh                 # prices + macro (최신 시세 갱신, 권장)
  sp-refresh all             # prices + macro + sectors + us-fund
  sp-refresh prices macro sectors us-fund   # 원하는 항목만
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

MACRO_TICKERS = {"^GSPC": "SP500.json", "^VIX": "VIX.json", "^TNX": "US10Y.json",
                 "^KS11": "KOSPI.json", "KRW=X": "USDKRW.json", "CL=F": "OIL.json"}


def _universe_codes():
    """기존 universe 파일명에서 종목 추출(KR=6자리코드, US=티커)."""
    files = sorted((RAW / "universe").glob("*.json"))
    kr, us = [], []
    for f in files:
        (kr if f.stem.isdigit() else us).append(f.stem)
    return kr, us


def _yf_ticker(code: str) -> str:
    return f"{code}.KS" if code.isdigit() else code


def _write_price(df, path: Path) -> int:
    """yfinance history DataFrame → 기존 MCP 포맷 {"result":"[{Date,Open,...}]"}."""
    recs = []
    for ts, row in df.iterrows():
        recs.append({
            "Date": ts.isoformat(),
            "Open": float(row["Open"]), "High": float(row["High"]),
            "Low": float(row["Low"]), "Close": float(row["Close"]),
            "Volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
            "Dividends": float(row.get("Dividends", 0) or 0),
            "Stock Splits": float(row.get("Stock Splits", 0) or 0),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"result": json.dumps(recs)}), encoding="utf-8")
    return len(recs)


def refresh_prices(period: str = "5y") -> None:
    import yfinance as yf
    kr, us = _universe_codes()
    print(f"[prices] 유니버스 {len(kr)+len(us)}종목(KR {len(kr)} + US {len(us)}) {period} 갱신…")
    ok = 0
    for code in kr + us:
        try:
            df = yf.Ticker(_yf_ticker(code)).history(period=period, auto_adjust=False)
            if df.empty:
                print(f"  - {code}: 데이터 없음"); continue
            n = _write_price(df, RAW / "universe" / f"{code}.json")
            ok += 1
        except Exception as e:
            print(f"  - {code}: 실패 {str(e)[:80]}")
    print(f"[prices] 완료 {ok}/{len(kr)+len(us)}")


def refresh_macro(period: str = "5y") -> None:
    import yfinance as yf
    print(f"[macro] 지수·환율 {len(MACRO_TICKERS)}종 {period} 갱신…")
    for tk, fn in MACRO_TICKERS.items():
        try:
            df = yf.Ticker(tk).history(period=period, auto_adjust=False)
            if df.empty:
                print(f"  - {tk}: 데이터 없음"); continue
            _write_price(df, RAW / "macro" / fn)
        except Exception as e:
            print(f"  - {tk}: 실패 {str(e)[:80]}")
    print("[macro] 완료")


def refresh_sectors() -> None:
    import yfinance as yf
    kr, us = _universe_codes()
    out = {}
    print(f"[sectors] {len(kr)+len(us)}종목 섹터 조회…")
    for code in kr + us:
        try:
            info = yf.Ticker(_yf_ticker(code)).info
            out[code] = {"sector": info.get("sector"), "industry": info.get("industry")}
        except Exception as e:
            out[code] = {"sector": None, "industry": None}
            print(f"  - {code}: 실패 {str(e)[:60]}")
    p = RAW / "meta" / "sectors.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[sectors] 완료 → {p}")


def _fin_year_records(inc, bal, shares):
    """yfinance income/balance(열=기간말) → reports/quarters 리스트."""
    import pandas as pd
    rows = []
    for col in inc.columns:
        if col not in bal.columns:
            continue
        d = pd.Timestamp(col)
        def g(df, key):
            try:
                v = df.loc[key, col]
                return None if v != v else float(v)
            except KeyError:
                return None
        rev, ni = g(inc, "Total Revenue"), g(inc, "Net Income")
        assets = g(bal, "Total Assets")
        eq = g(bal, "Stockholders Equity") or g(bal, "Total Equity Gross Minority Interest")
        if None in (rev, ni, assets, eq):
            continue
        rows.append({"period_end": d, "revenue": rev, "op_income": g(inc, "Operating Income"),
                     "net_income": ni, "assets": assets, "equity": eq,
                     "liabilities": assets - eq})
    return rows


def refresh_us_fundamentals() -> None:
    import pandas as pd
    import yfinance as yf
    _, us = _universe_codes()
    print(f"[us-fund] 미국 {len(us)}종목 재무(연간+분기) 갱신…")
    for t in us:
        try:
            tk = yf.Ticker(t)
            shares = (tk.info or {}).get("sharesOutstanding")
            # 연간
            ann = _fin_year_records(tk.income_stmt, tk.balance_sheet, shares)
            reports = [{"fiscal_year": r["period_end"].year,
                        "disclosed_at": (r["period_end"] + pd.Timedelta(days=75)).date().isoformat(),
                        "revenue": r["revenue"], "op_income": r["op_income"],
                        "net_income": r["net_income"], "assets": r["assets"],
                        "liabilities": r["liabilities"], "equity": r["equity"]}
                       for r in ann]
            (RAW / "fundamentals" / f"{t}.json").write_text(json.dumps(
                {"stock_code": t, "name": t, "corp_code": None,
                 "shares_outstanding": shares, "reports": reports}, ensure_ascii=False))
            # 분기(단독)
            q = _fin_year_records(tk.quarterly_income_stmt, tk.quarterly_balance_sheet, shares)
            quarters = [{"period_end": r["period_end"].date().isoformat(),
                         "revenue": r["revenue"], "op_income": r["op_income"],
                         "net_income": r["net_income"], "assets": r["assets"],
                         "equity": r["equity"]} for r in q]
            (RAW / "fundamentals_q" / f"{t}.json").write_text(json.dumps(
                {"stock_code": t, "market": "US", "cumulative": False,
                 "quarters": quarters}, ensure_ascii=False))
        except Exception as e:
            print(f"  - {t}: 실패 {str(e)[:80]}")
    print("[us-fund] 완료 (한국 재무는 DART 키 필요 — 기존 스냅샷 유지)")


def main() -> None:
    args = [a.lower() for a in sys.argv[1:]] or ["prices", "macro"]
    if "all" in args:
        args = ["prices", "macro", "sectors", "us-fund"]
    print("=" * 64)
    print("주탐주예 데이터 최신화 (로컬 전용 · yfinance) — 클라우드선 차단됨")
    print("=" * 64)
    if "prices" in args:
        refresh_prices()
    if "macro" in args:
        refresh_macro()
    if "sectors" in args:
        refresh_sectors()
    if "us-fund" in args:
        refresh_us_fundamentals()
    print("\n완료. 확인: sp-picks 60  /  발송: sp-notify 60")
    print("한국 재무·감성 갱신은 분기성(키 필요) — 자세한 건 README 참조.")


if __name__ == "__main__":
    main()
