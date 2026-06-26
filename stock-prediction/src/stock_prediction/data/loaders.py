"""raw → interim → processed 변환 오케스트레이션.

- load_raw:    collectors 호출 결과를 data/raw 에 parquet 저장 (불변)
- build_interim: 정합(영업일 정렬)·결측·이상치 처리
- build_features_matrix: 피처 결합 → data/processed 학습 매트릭스
"""
from __future__ import annotations

import pandas as pd


def build_features_matrix(cfg: dict) -> pd.DataFrame:
    """설정에 따라 가격/재무/거시/심리 피처를 결합한 학습용 매트릭스 반환.

    핵심 규약: 모든 조인은 시점 t 이전 정보만(look-ahead 방지).
    재무는 disclosed_at <= t, 심리는 발행시각 <= t.
    """
    raise NotImplementedError("loaders 구현 예정 — README 설계원칙 참조")
