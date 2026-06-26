"""백테스트 엔진: 모델 예측 → 상위 K종목 포지션 → 거래비용 차감 수익률 시뮬.
config.backtest(top_k, rebalance, cost_bps) 사용.
"""
from __future__ import annotations


def run_backtest(predictions, prices, cfg) -> dict:
    """누적수익률·MDD·샤프 등 성과 dict 반환."""
    raise NotImplementedError
