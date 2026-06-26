"""writing.citations / writing.export 순수 로직 단위 테스트(오프라인)."""

from __future__ import annotations

from literature_review.writing import citations
from literature_review.writing import export


SAMPLE_WORK = {
    "id": "https://openalex.org/W123",
    "title": "Large Language Models in Education",
    "publication_year": 2023,
    "doi": "https://doi.org/10.1000/abc",
    "cited_by_count": 42,
    "primary_location": {"source": {"display_name": "Journal of AI Ed"}},
    "authorships": [
        {"author": {"display_name": "Min Su Kim"}},
        {"author": {"display_name": "Jane Doe"}},
    ],
    "abstract_inverted_index": {"This": [0], "is": [1], "study": [3], "a": [2]},
}

SAMPLE_ROW = {
    "title": "Korean NLP Survey",
    "year": 2021,
    "authors": "Hong Gil Dong, Lee Soon Shin",
    "venue": "KCI Journal",
    "cited_by": 7,
    "doi": "https://doi.org/10.2000/xyz",
    "url": "https://openalex.org/W999",
}


def test_clean_doi_strips_prefix():
    assert citations.clean_doi("https://doi.org/10.1/x") == "10.1/x"
    assert citations.clean_doi("https://dx.doi.org/10.1/x") == "10.1/x"
    assert citations.clean_doi(None) == ""


def test_reconstruct_abstract_orders_by_position():
    assert citations.reconstruct_abstract(SAMPLE_WORK["abstract_inverted_index"]) == "This is a study"
    assert citations.reconstruct_abstract(None) == ""


def test_split_name_heuristic():
    assert citations.split_name("Jane Doe") == {"family": "Doe", "given": "Jane"}
    assert citations.split_name("Min Su Kim") == {"family": "Kim", "given": "Min Su"}
    assert citations.split_name("Cher") == {"literal": "Cher"}


def test_work_to_csl_full_metadata():
    item = citations.work_to_csl(SAMPLE_WORK, country="US")
    assert item["title"] == "Large Language Models in Education"
    assert item["DOI"] == "10.1000/abc"
    assert item["container-title"] == "Journal of AI Ed"
    assert item["issued"] == {"date-parts": [[2023]]}
    assert item["author"][0] == {"family": "Kim", "given": "Min Su"}
    assert item["abstract"] == "This is a study"
    assert item["custom"]["cited_by_count"] == 42
    assert item["custom"]["country"] == "US"


def test_row_to_csl_degraded():
    item = citations.row_to_csl(SAMPLE_ROW, country="KR")
    assert item["DOI"] == "10.2000/xyz"
    assert [a["family"] for a in item["author"]] == ["Dong", "Shin"]
    assert item["issued"] == {"date-parts": [[2021]]}
    assert item["custom"]["country"] == "KR"


def test_make_key_unique():
    used: set[str] = set()
    a = citations.work_to_csl(SAMPLE_WORK)
    k1 = citations.make_key(a, used)
    k2 = citations.make_key(a, used)  # 같은 항목 → 충돌 회피
    assert k1 == "kim2023large"
    assert k2 == "kim2023largea"
    assert k1 != k2


def test_csl_to_bibtex_emits_entry():
    bib = citations.csl_to_bibtex([citations.work_to_csl(SAMPLE_WORK)])
    assert "@article{kim2023large," in bib
    assert "author = {Kim, Min Su and Doe, Jane}" in bib
    assert "doi = {10.1000/abc}" in bib
    assert "year = {2023}" in bib


def test_merge_pool_dedupes_by_doi_keeping_most_cited():
    low = citations.work_to_csl(SAMPLE_WORK)
    low["custom"]["cited_by_count"] = 5
    high = citations.work_to_csl(SAMPLE_WORK)
    high["custom"]["cited_by_count"] = 99
    merged = export.merge_pool([low], [high])
    assert len(merged) == 1
    assert merged[0]["custom"]["cited_by_count"] == 99


def test_render_brief_lists_sources_and_topic():
    items = [citations.work_to_csl(SAMPLE_WORK, country="US")]
    brief = export.render_brief("LLM in education", items)
    assert "# 논문 작성 브리프: LLM in education" in brief
    assert "Large Language Models in Education" in brief
    assert "인용 위조 금지" in brief
