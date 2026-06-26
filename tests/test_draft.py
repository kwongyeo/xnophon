"""writing.draft 순수 로직 단위 테스트(오프라인, LLM 호출 없음)."""

from __future__ import annotations

from literature_review.writing import citations, draft


def _pool():
    work = {
        "id": "https://openalex.org/W1",
        "title": "Large Language Models in Education",
        "publication_year": 2023,
        "doi": "https://doi.org/10.1/x",
        "cited_by_count": 42,
        "primary_location": {"source": {"display_name": "Journal of AI Ed"}},
        "authorships": [{"author": {"display_name": "Min Su Kim"}}],
    }
    item = citations.work_to_csl(work, country="US")
    return [item]


def test_ensure_ids_assigns_unique_keys():
    items = _pool() + _pool()  # 동일 항목 2개
    draft._ensure_ids(items)
    assert items[0]["id"] == "kim2023large"
    assert items[1]["id"] != items[0]["id"]


def test_reference_lines_format():
    items = _pool()
    draft._ensure_ids(items)
    line = draft.reference_lines(items)[0]
    assert line.startswith("[kim2023large] Min Su Kim (2023).")
    assert "[US]" in line
    assert "doi:10.1/x" in line


def test_build_messages_enforces_constraints():
    items = _pool()
    draft._ensure_ids(items)
    system, user = draft.build_messages("LLM 교육", items)
    assert "인용 위조 금지" in system
    assert "[key]" in system
    assert "한국(KR)" in system and "미국(US)" in system
    assert "LLM 교육" in user
    assert "[kim2023large]" in user  # 인용 풀이 프롬프트에 포함


def test_skeleton_draft_has_all_sections_and_refs():
    items = _pool()
    draft._ensure_ids(items)
    md = draft.skeleton_draft("LLM 교육", items)
    assert "# LLM 교육" in md
    for sec in draft.SECTIONS:
        assert f"## {sec}" in md
    assert "## References" in md
    assert "[kim2023large]" in md
