"""펀더멘털 PIT 결합 테스트 — 공시 전에는 재무가 보이면 안 된다(누수 방지)."""
import numpy as np
import pandas as pd

from stock_prediction.features.fundamental import (FUND_FEATURE_COLUMNS,
                                                   add_fundamental_features)


def test_point_in_time_join_no_leakage():
    dates = pd.bdate_range("2024-01-01", periods=200)
    prices = pd.DataFrame({
        "date": dates, "ticker": "005930",
        "adj_close": np.linspace(100, 200, len(dates)),
    })
    # 공시일: 2024-03-15. 그 이전에는 재무 NaN, 이후에는 값 존재해야 함.
    snaps = pd.DataFrame([{
        "ticker": "005930", "disclosed_at": pd.Timestamp("2024-03-15"),
        "f_roe": 0.08, "f_op_margin": 0.1, "f_liab_to_equity": 0.3,
        "f_rev_growth": 0.05, "bps": 50.0, "eps": 5.0,
    }])
    out = add_fundamental_features(prices, snaps)

    before = out[out["date"] < "2024-03-15"]
    after = out[out["date"] >= "2024-03-15"]
    assert before["f_roe"].isna().all()         # 공시 전 누수 없음
    assert (after["f_roe"] == 0.08).all()        # 공시 후 값 적용
    # 가치 팩터: bps/price, 가격 상승 → book_to_price 하락
    assert (after["f_book_to_price"] == 50.0 / after["adj_close"]).all()
    for c in FUND_FEATURE_COLUMNS:
        assert c in out.columns
