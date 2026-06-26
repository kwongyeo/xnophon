"""0단계 PoC — 삼성전자·AAPL 시세+재무 실제 수집 → 정규화 → 피처/타깃 → 저장.

목적: 수집→정규화→피처→타깃→저장의 end-to-end 골격을 실제 데이터로 검증한다.

데이터 출처(이 환경):
  - 시세: MCP UsStockInfo(yfinance 백엔드)로 받은 원본을 data/raw 에 저장해 둠.
          (샌드박스 프록시가 Yahoo/Naver 직접 접속을 차단하므로 MCP 경유)
  - AAPL 재무: MCP UsStockInfo 분기 손익/재무상태표
  - 삼성 재무: MCP OpenDART 2024 사업보고서(연결)
운영 환경에서는 collectors 의 fetch_* (yfinance / OpenDART REST)가 동일 출력을 만든다.

실행: sp-poc   (또는  python -m stock_prediction.poc)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import load_config
from .data.collectors import dart, yfinance_us
from .features.technical import FEATURE_COLUMNS, add_technical_features

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"

# (표시이름, 티커, 원본 시세 파일)
ASSETS = [
    ("Apple", "AAPL", "aapl_price.json"),
    ("Samsung", "005930.KS", "samsung_price.json"),
]


def build_target(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """미래 h일 수익률 타깃. 마지막 h행은 NaN(미래 미관측)."""
    df = df.sort_values("date").copy()
    df[f"target_ret_{horizon}d"] = df["adj_close"].shift(-horizon) / df["adj_close"] - 1
    return df


def build_price_panel(cfg: dict) -> pd.DataFrame:
    """두 종목 시세를 정규화하고 기술적 피처 + 타깃을 붙여 결합."""
    horizon = cfg["target"]["horizon"]
    frames = []
    for name, ticker, fname in ASSETS:
        raw = yfinance_us.load_raw(RAW / fname)
        px = yfinance_us.normalize_price(raw, ticker)
        px = add_technical_features(px)
        px = build_target(px, horizon)
        px.insert(1, "name", name)
        frames.append(px)
    return pd.concat(frames, ignore_index=True)


def build_fundamentals() -> pd.DataFrame:
    """AAPL(yfinance) + 삼성(OpenDART) 재무를 표준 스키마로 결합하고 비율을 계산."""
    aapl = yfinance_us.normalize_financials(
        yfinance_us.load_raw(RAW / "aapl_income.json"),
        yfinance_us.load_raw(RAW / "aapl_balance.json"),
        ticker="AAPL",
    )
    sams = dart.normalize_financials(
        dart.load_raw(RAW / "samsung_financials_2024.json"), ticker="005930.KS"
    )
    fund = pd.concat([aapl, sams], ignore_index=True)
    fund["roe"] = fund["net_income"] / fund["total_equity"]
    fund["operating_margin"] = fund["operating_income"] / fund["revenue"]
    fund["debt_to_equity"] = fund["total_debt"] / fund["total_equity"]
    return fund


def main() -> None:
    cfg = load_config()
    h = cfg["target"]["horizon"]
    PROCESSED.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("0단계 PoC — 삼성전자 · AAPL 시세+재무 수집/정규화")
    print("=" * 64)

    panel = build_price_panel(cfg)
    fund = build_fundamentals()

    print("\n[1] 시세 패널 (정규화 + 기술적피처 + 타깃)")
    for name, ticker, _ in ASSETS:
        sub = panel[panel["ticker"] == ticker]
        print(f"  - {name:8s}({ticker}): {len(sub):4d}행 "
              f"{sub['date'].min().date()} ~ {sub['date'].max().date()}, "
              f"최근 종가 {sub['adj_close'].iloc[-1]:,.2f}")
    print(f"  피처: {FEATURE_COLUMNS}")
    print(f"  타깃: target_ret_{h}d (미래 {h}영업일 수익률)")

    print("\n  최근 5행 (AAPL) — 누수 없는 피처 + 미래타깃:")
    cols = ["date", "adj_close", "ret_1d", "ma_ratio", "rsi_14", f"target_ret_{h}d"]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(panel[panel["ticker"] == "AAPL"][cols].tail(5).to_string(index=False))

    print("\n[2] 펀더멘털 (정규화 + 비율)")
    fcols = ["ticker", "fiscal_period", "disclosed_at", "revenue",
             "operating_margin", "roe", "debt_to_equity"]
    with pd.option_context("display.width", 200, "display.max_columns", 20,
                           "display.float_format", lambda x: f"{x:,.3f}"):
        print(fund[fcols].to_string(index=False))

    panel.to_parquet(PROCESSED / "poc_price_panel.parquet", index=False)
    fund.to_parquet(PROCESSED / "poc_fundamentals.parquet", index=False)
    print(f"\n[3] 저장 완료 → {PROCESSED}/")
    print("    - poc_price_panel.parquet")
    print("    - poc_fundamentals.parquet")
    print("\n다음 단계: 단계1 베이스라인(가격 피처 → LightGBM) — README 로드맵 참조")


if __name__ == "__main__":
    main()
