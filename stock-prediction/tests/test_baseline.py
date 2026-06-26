"""단계1 모듈 테스트: 워크포워드 분할, 지표, 백테스트 엔진, 누수 점검."""
import numpy as np
import pandas as pd

from stock_prediction.backtest import engine
from stock_prediction.backtest.splitter import walk_forward_splits
from stock_prediction.evaluation import metrics


def test_walk_forward_no_overlap_and_embargo():
    dates = pd.bdate_range("2020-01-01", periods=300)
    folds = walk_forward_splits(dates, train_window=120, test_window=20,
                                step=20, embargo=5)
    assert len(folds) > 0
    for f in folds:
        # test는 항상 train 이후 (embargo 공백 포함)
        assert f.test_start > f.train_end
        gap = np.busday_count(f.train_end.date(), f.test_start.date())
        assert gap >= 5  # embargo 거래일 이상 떨어져 있어야 함


def test_metrics_basic():
    # 완전 상관 → IC=1
    pred = np.array([1.0, 2, 3, 4, 5])
    actual = np.array([1.0, 2, 3, 4, 5])
    assert abs(metrics.information_coefficient(pred, actual) - 1.0) < 1e-9
    assert abs(metrics.rank_ic(pred, actual) - 1.0) < 1e-9
    assert metrics.directional_accuracy([1, -1, 1], [1, -1, -1]) == 2 / 3
    eq = pd.Series([1.0, 1.2, 0.9, 1.5])
    assert metrics.max_drawdown(eq) < 0


def test_backtest_perfect_foresight_beats_benchmark():
    # pred == fwd_ret(완벽 예측)이면 상위 K 선택 전략이 벤치마크 평균을 이겨야 함
    rng = np.random.default_rng(0)
    rows = []
    for d in pd.bdate_range("2021-01-01", periods=60):
        for t in range(10):
            r = rng.normal(0, 0.05)
            rows.append({"date": d, "ticker": f"T{t}", "pred": r, "fwd_ret": r})
    df = pd.DataFrame(rows)
    res = engine.run_backtest(df, horizon=5, top_k=3, cost_bps=0)
    assert res["ic"] > 0.99
    assert res["strategy"]["total_return"] > res["benchmark"]["total_return"]
