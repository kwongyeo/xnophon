"""KCI(한국학술지인용색인) Open API 어댑터.

영문 DB(OpenAlex)가 잘 다루지 못하는 한국어 인문·사회과학 논문을 보강한다.
키 발급·등록 절차는 ``docs/kci-api-setup.md`` 참조.

KCI API는 GET 방식, XML 응답이 기본이다.

    https://open.kci.go.kr/po/openapi/openApiSearch.kci
        ?apiCode=articleSearch&key=<KEY>&displayCount=20&page=1&title=<검색어>

응답 XML 스키마는 네임스페이스/세부 태그가 버전에 따라 다를 수 있어,
:func:`parse_search_xml` 은 태그 이름의 localname을 유연하게 매칭한다.
순수 파서라 네트워크 없이 단위 테스트가 가능하다.
"""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from literature_review.sources.openalex import PaperRow

KCI_BASE = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"


def _localname(tag: str) -> str:
    """``{ns}article-title`` → ``article-title``."""
    return tag.rsplit("}", 1)[-1].lower()


def _find_first(elem: ET.Element, *names: str) -> str:
    """후손 중 localname이 names 중 하나인 첫 요소의 텍스트(공백 정리)."""
    targets = {n.lower() for n in names}
    for node in elem.iter():
        if _localname(node.tag) in targets and (node.text or "").strip():
            return node.text.strip()
    return ""


def _find_all_text(elem: ET.Element, *names: str) -> list[str]:
    targets = {n.lower() for n in names}
    out = []
    for node in elem.iter():
        if _localname(node.tag) in targets and (node.text or "").strip():
            out.append(node.text.strip())
    return out


def _record_to_row(rec: ET.Element) -> PaperRow:
    # 제목: 한국어 우선이나, 태그 순서대로 첫 번째를 채택.
    title = _find_first(rec, "article-title", "title") or "(제목 없음)"
    authors = _find_all_text(rec, "author")
    year_str = _find_first(rec, "year", "pub-year", "publication-year")
    try:
        year: int | None = int(year_str[:4]) if year_str else None
    except ValueError:
        year = None
    venue = _find_first(rec, "journal-name", "journal-title", "journal")
    doi = _find_first(rec, "doi")
    url = _find_first(rec, "url", "link")
    cited = _find_first(rec, "citation-count", "cited-count", "citationCount")
    try:
        cited_by = int(cited) if cited else 0
    except ValueError:
        cited_by = 0
    return {
        "title": title,
        "year": year,
        "authors": ", ".join(authors[:3]),
        "venue": venue,
        "cited_by": cited_by,
        "doi": doi,
        "url": url,
    }


def parse_search_xml(xml_text: str) -> list[PaperRow]:
    """KCI articleSearch XML → PaperRow 목록(순수, 네트워크 불필요)."""
    root = ET.fromstring(xml_text)
    records = [
        node
        for node in root.iter()
        if _localname(node.tag) in {"articleinfo", "record", "article"}
    ]
    # articleInfo 가 record 안에 중첩될 수 있어, 더 구체적인 articleInfo 우선.
    article_infos = [n for n in records if _localname(n.tag) == "articleinfo"]
    chosen = article_infos or records
    rows = [_record_to_row(r) for r in chosen]
    # 제목이 비어있지 않은 것만.
    return [r for r in rows if r["title"] and r["title"] != "(제목 없음)"] or rows


def _build_url(query: str, count: int, page: int, key: str) -> str:
    params = {
        "apiCode": "articleSearch",
        "key": key,
        "displayCount": max(1, min(count, 100)),
        "page": max(1, page),
        "title": query,
    }
    return f"{KCI_BASE}?{urllib.parse.urlencode(params)}"


def search(query: str, count: int = 20, page: int = 1, *, timeout: int = 15) -> list[PaperRow]:
    """KCI에서 제목 검색해 PaperRow 목록 반환. KCI_API_KEY 필요."""
    key = os.environ.get("KCI_API_KEY")
    if not key:
        raise RuntimeError(
            "KCI_API_KEY 미설정. docs/kci-api-setup.md 를 참고해 키를 발급·등록하세요."
        )
    url = _build_url(query, count, page, key)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (신뢰된 고정 호스트)
        xml_text = resp.read().decode("utf-8", errors="replace")
    return parse_search_xml(xml_text)


def search_csl(query: str, count: int = 20, page: int = 1) -> list[dict[str, Any]]:
    """KCI 검색 결과를 CSL-JSON 항목으로 반환(country='KR' 태깅)."""
    from literature_review.writing import citations

    return [citations.row_to_csl(r, country="KR") for r in search(query, count, page)]
