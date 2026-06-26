"""섹터 메타데이터 로더 (data/raw/meta/sectors.json).

sectors.json: {"005930": {"sector":"Technology","industry":"..."}, "AAPL": {...}, ...}
yfinance get_stock_info의 GICS식 sector를 KR·US 공통으로 사용.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_sectors(path: str | Path) -> dict[str, str]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: (v.get("sector") or "Unknown") for k, v in obj.items()}


def add_sector(panel: pd.DataFrame, path: str | Path) -> pd.DataFrame:
    panel = panel.copy()
    panel["sector"] = panel["ticker"].map(load_sectors(path)).fillna("Unknown")
    return panel
