"""거시지표 수집기 (FRED / 한국은행 ECOS).

금리·환율·물가·지수 등 시장 레짐 피처의 원천. docs §3 참조.
"""
from __future__ import annotations

import pandas as pd


def fetch_fred(series_id: str, start: str, end: str) -> pd.DataFrame:
    """FRED 시계열 (예: DGS10, CPIAUCSL, FEDFUNDS)."""
    raise NotImplementedError


def fetch_ecos(stat_code: str, start: str, end: str) -> pd.DataFrame:
    """한국은행 ECOS 시계열 (기준금리, 환율 등)."""
    raise NotImplementedError
