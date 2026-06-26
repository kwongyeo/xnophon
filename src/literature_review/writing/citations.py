"""인용 변환기 — OpenAlex 데이터 → CSL-JSON / BibTeX.

순수 함수 모듈(외부 네트워크·pyalex 의존 없음)이라 단위 테스트가 쉽다.

CSL-JSON은 Zotero·Pandoc·대다수 논문 작성 도구(opendraft 포함)가 공통으로
이해하는 인용 표준 포맷이다. 이 모듈은 두 가지 입력을 모두 받는다.

- ``work``  : OpenAlex API의 원본 work dict (저자 전체·초록·DOI 보존)
- ``row``   : :data:`literature_review.sources.openalex.PaperRow` (축약본)

원본 work가 있으면 가능한 한 풍부하게, 없으면 축약본으로 degrade한다.
"""

from __future__ import annotations

import re
from typing import Any

_WORD_RE = re.compile(r"[a-z0-9]+")
_DOI_PREFIX_RE = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)


def clean_doi(doi: str | None) -> str:
    """``https://doi.org/10.x`` → ``10.x``. 없으면 빈 문자열."""
    if not doi:
        return ""
    return _DOI_PREFIX_RE.sub("", doi.strip())


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex의 abstract_inverted_index를 평문 초록으로 복원."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(word for _, word in positions)


def split_name(display_name: str) -> dict[str, str]:
    """표시 이름을 CSL author 객체(family/given)로 분리.

    마지막 토큰을 성(family)으로 간주하는 휴리스틱. 단일 토큰이면 literal로 둔다.
    """
    name = (display_name or "").strip()
    if not name:
        return {"literal": ""}
    parts = name.split()
    if len(parts) == 1:
        return {"literal": name}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def work_to_csl(work: dict[str, Any], country: str | None = None) -> dict[str, Any]:
    """OpenAlex 원본 work → CSL-JSON 항목."""
    authorships = work.get("authorships") or []
    authors = [
        split_name(a.get("author", {}).get("display_name", ""))
        for a in authorships
        if a.get("author")
    ]
    year = work.get("publication_year")
    venue = (
        (work.get("primary_location") or {}).get("source") or {}
    ).get("display_name") or ""
    item: dict[str, Any] = {
        "type": "article-journal",
        "title": work.get("title") or "(제목 없음)",
        "author": authors or [{"literal": "Anonymous"}],
        "container-title": venue,
        "DOI": clean_doi(work.get("doi")),
        "URL": work.get("id", ""),
    }
    if year:
        item["issued"] = {"date-parts": [[year]]}
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    if abstract:
        item["abstract"] = abstract
    item["custom"] = {
        "cited_by_count": work.get("cited_by_count", 0),
        "country": country or "",
        "source": "openalex",
    }
    return item


def row_to_csl(row: dict[str, Any], country: str | None = None) -> dict[str, Any]:
    """PaperRow(축약본) → CSL-JSON 항목. 저자 문자열을 분해한다."""
    raw_authors = [a.strip() for a in (row.get("authors") or "").split(",") if a.strip()]
    authors = [split_name(a) for a in raw_authors] or [{"literal": "Anonymous"}]
    item: dict[str, Any] = {
        "type": "article-journal",
        "title": row.get("title") or "(제목 없음)",
        "author": authors,
        "container-title": row.get("venue") or "",
        "DOI": clean_doi(row.get("doi")),
        "URL": row.get("url", ""),
    }
    if row.get("year"):
        item["issued"] = {"date-parts": [[row["year"]]]}
    item["custom"] = {
        "cited_by_count": row.get("cited_by", 0),
        "country": country or "",
        "source": "openalex",
    }
    return item


def _author_family(item: dict[str, Any]) -> str:
    authors = item.get("author") or []
    if not authors:
        return "anon"
    first = authors[0]
    name = first.get("family") or first.get("literal") or "anon"
    token = _WORD_RE.findall(name.lower())
    return token[0] if token else "anon"


def _year_of(item: dict[str, Any]) -> str:
    parts = (item.get("issued") or {}).get("date-parts") or [[]]
    if parts and parts[0]:
        return str(parts[0][0])
    return "nd"


def make_key(item: dict[str, Any], used: set[str]) -> str:
    """``family + year + 제목첫단어`` 형태의 고유 BibTeX 키 생성."""
    family = _author_family(item)
    year = _year_of(item)
    title_words = _WORD_RE.findall((item.get("title") or "").lower())
    head = title_words[0] if title_words else ""
    base = f"{family}{year}{head}" or "ref"
    key = base
    suffix = ord("a")
    while key in used:
        key = f"{base}{chr(suffix)}"
        suffix += 1
    used.add(key)
    return key


def _bibtex_authors(item: dict[str, Any]) -> str:
    names = []
    for a in item.get("author") or []:
        if a.get("literal"):
            names.append(a["literal"])
        else:
            family = a.get("family", "")
            given = a.get("given", "")
            names.append(f"{family}, {given}".strip().strip(","))
    return " and ".join(n for n in names if n)


def _bibtex_escape(value: str) -> str:
    return (value or "").replace("{", "").replace("}", "").replace("\\", "")


def item_to_bibtex(item: dict[str, Any], key: str) -> str:
    """단일 CSL 항목을 BibTeX @article 엔트리로 직렬화."""
    fields: list[tuple[str, str]] = []
    authors = _bibtex_authors(item)
    if authors:
        fields.append(("author", authors))
    fields.append(("title", _bibtex_escape(item.get("title", ""))))
    venue = item.get("container-title")
    if venue:
        fields.append(("journal", _bibtex_escape(venue)))
    year = _year_of(item)
    if year != "nd":
        fields.append(("year", year))
    if item.get("DOI"):
        fields.append(("doi", item["DOI"]))
    if item.get("URL"):
        fields.append(("url", item["URL"]))
    body = ",\n".join(f"  {name} = {{{val}}}" for name, val in fields)
    return f"@article{{{key},\n{body}\n}}"


def csl_to_bibtex(items: list[dict[str, Any]]) -> str:
    """CSL 항목 목록 → 전체 .bib 텍스트. 키는 항목 순서대로 고유 보장."""
    used: set[str] = set()
    entries = []
    for item in items:
        key = make_key(item, used)
        item.setdefault("id", key)
        entries.append(item_to_bibtex(item, key))
    return "\n\n".join(entries) + ("\n" if entries else "")
