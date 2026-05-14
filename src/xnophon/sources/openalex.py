"""OpenAlex API 어댑터.

OpenAlex (https://openalex.org)는 2억+ 논문 메타데이터를 무료 제공한다.
ISO 국가 코드로 저자 국적 필터링이 가능해 한·미 비교에 적합하다.
"""

from __future__ import annotations

import os
from typing import TypedDict

from pyalex import Works, config as pyalex_config

# polite pool 이메일은 환경변수가 있으면 그것을, 없으면 기본값 사용.
pyalex_config.email = os.environ.get("OPENALEX_EMAIL", "kwongyeo@gmail.com")


class PaperRow(TypedDict):
    title: str
    year: int | None
    authors: str
    venue: str
    cited_by: int
    doi: str
    url: str


def search(query: str, country: str, from_year: int = 2020, per_page: int = 15) -> list[PaperRow]:
    """주제어와 국가 코드(KR/US 등)로 논문을 검색해 인용수 내림차순으로 반환."""
    works = (
        Works()
        .search(query)
        .filter(authorships={"countries": country})
        .filter(from_publication_date=f"{from_year}-01-01")
        .sort(cited_by_count="desc")
        .get(per_page=per_page)
    )
    return [_to_row(w) for w in works]


def _to_row(w: dict) -> PaperRow:
    authors = ", ".join(
        a["author"]["display_name"] for a in (w.get("authorships") or [])[:3]
    )
    return {
        "title": w.get("title") or "(제목 없음)",
        "year": w.get("publication_year"),
        "authors": authors,
        "venue": (w.get("primary_location") or {}).get("source", {}).get("display_name", "") or "",
        "cited_by": w.get("cited_by_count", 0),
        "doi": w.get("doi") or "",
        "url": w.get("id", ""),
    }
