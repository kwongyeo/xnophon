"""수집기 정규화 테스트 (data/raw 원본 → 표준 스키마)."""
from pathlib import Path

import pytest

from stock_prediction.data.collectors import dart, yfinance_us
from stock_prediction.data.schema import FUNDAMENTAL_COLUMNS, PRICE_COLUMNS
from stock_prediction.features.technical import add_technical_features

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_dart_normalize_samsung():
    f = RAW / "samsung_financials_2024.json"
    if not f.exists():
        pytest.skip("samsung_financials_2024.json 없음")
    df = dart.normalize_financials(dart.load_raw(f), ticker="005930.KS")
    assert list(df.columns) == FUNDAMENTAL_COLUMNS
    cur = df[df["fiscal_period"] == "2024"].iloc[0]
    # 삼성전자 2024 연결: 매출 약 300조, 자산총계 약 514조 (DART 실제값)
    assert cur["revenue"] > 250e12
    assert cur["total_assets"] > 400e12
    assert cur["disclosed_at"] == "2025-03-11"  # rcept_no에서 추출


def test_price_normalize_and_features():
    f = RAW / "aapl_price.json"
    if not f.exists():
        pytest.skip("aapl_price.json 없음 (시세 수집 전)")
    px = yfinance_us.normalize_price(yfinance_us.load_raw(f), ticker="AAPL")
    assert list(px.columns) == PRICE_COLUMNS
    assert px["date"].is_monotonic_increasing
    feat = add_technical_features(px)
    # rolling 피처는 초기 구간 NaN, 후반부는 채워져야 함
    assert feat["ma_20"].tail(1).notna().all()
    assert feat["rsi_14"].tail(1).notna().all()
