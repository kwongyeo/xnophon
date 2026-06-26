"""한국 재무·공시 수집기 (OpenDART).

DART_API_KEY 필요(무료). 프로토타이핑은 MCP opendart 도구로 대체 가능(docs §2).
공시 "공개일"을 disclosed_at 으로 반드시 기록 — point-in-time 정렬에 사용.
"""
from __future__ import annotations

import pandas as pd


def fetch_financials(corp_code: str, year: int) -> pd.DataFrame:
    """전체 재무제표 → schema.FUNDAMENTAL_COLUMNS."""
    raise NotImplementedError("OpenDART 연동 구현 예정 — docs/data-sources.md §2 참조")


def fetch_disclosures(corp_code: str, start: str, end: str) -> pd.DataFrame:
    """공시 이벤트(증자/합병 등) 목록. 이벤트 더미 피처로 활용."""
    raise NotImplementedError
