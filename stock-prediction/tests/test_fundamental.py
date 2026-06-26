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


def test_quarterly_ttm_cumulative_to_standalone(tmp_path):
    """KR 누적 분기 → 단독 → TTM 합산 검증."""
    import json
    from stock_prediction.features.fundamental import load_fundamentals_quarterly
    qdir = tmp_path / "q"; adir = tmp_path / "a"
    qdir.mkdir(); adir.mkdir()
    # 연간(FY)=Q4 누적: 2023 FY revenue=400(ni=40), 2024 FY=440(ni=44)
    (adir / "T.json").write_text(json.dumps({
        "stock_code": "T", "shares_outstanding": 100,
        "reports": [
            {"fiscal_year": 2023, "disclosed_at": "2024-03-15", "revenue": 400,
             "op_income": 40, "net_income": 40, "assets": 1000, "liabilities": 600, "equity": 400},
            {"fiscal_year": 2024, "disclosed_at": "2025-03-15", "revenue": 440,
             "op_income": 44, "net_income": 44, "assets": 1100, "liabilities": 650, "equity": 450},
        ]}))
    # 2024 분기 누적: Q1=100, Q2=210, Q3=330 (단독 100,110,120, Q4=440-330=110)
    (qdir / "T.json").write_text(json.dumps({
        "stock_code": "T", "market": "KR", "cumulative": True,
        "quarters": [
            {"period": "2024Q1", "disclosed_at": "2024-05-15", "revenue": 100, "op_income": 10,
             "net_income": 10, "assets": 1020, "liabilities": 610, "equity": 410},
            {"period": "2024Q2", "disclosed_at": "2024-08-14", "revenue": 210, "op_income": 21,
             "net_income": 21, "assets": 1040, "liabilities": 620, "equity": 420},
            {"period": "2024Q3", "disclosed_at": "2024-11-14", "revenue": 330, "op_income": 33,
             "net_income": 33, "assets": 1060, "liabilities": 630, "equity": 440},
        ]}))
    q = load_fundamentals_quarterly(qdir, adir)
    # 2024Q4 TTM(disclosed 2025-03-15) = 2024 단독 4분기 합 = FY2024 = 440
    q4 = q[q["disclosed_at"] == "2025-03-15"].iloc[0]
    assert abs(q4["revenue"] - 440) < 1e-9
    # 2024Q3 TTM = Q4_2023 + Q1+Q2+Q3_2024. Q4_2023=FY2023-9M_2023(없음) → 연속불가로 스킵 기대
    # → 최소한 BS는 분기말 시점값(2024Q4=FY2024 자산 1100)
    assert abs(q4["assets"] - 1100) < 1e-9
