"""뉴스·검색 트렌드 수집기 (Naver) → 감성 피처 원천.

기사 발행 시각 이전 사용 금지(누수). 출력은 schema.SENTIMENT_COLUMNS. docs §4 참조.
프로토타이핑은 MCP NaverSearch 도구로 대체 가능.
"""
from __future__ import annotations

import pandas as pd


def fetch_news(query: str, start: str, end: str) -> pd.DataFrame:
    """일자별 기사(제목/요약/발행시각). 감성모델 입력."""
    raise NotImplementedError


def fetch_search_trend(query: str, start: str, end: str) -> pd.DataFrame:
    """Naver DataLab 검색량 추이 → 관심도 피처."""
    raise NotImplementedError
