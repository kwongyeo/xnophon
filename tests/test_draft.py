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


_OUTLINE = {
    "title": "맞춤 제목",
    "sections": [
        {"heading": "서론", "subsections": []},
        {"heading": "선행연구", "subsections": ["한국(KR) 동향", "미국(US) 동향"]},
        {"heading": "AI 글쓰기 효과", "subsections": ["자동 피드백"]},
        {"heading": "결론", "subsections": []},
    ],
}


def test_skeleton_draft_follows_outline():
    items = _pool()
    draft._ensure_ids(items)
    md = draft.skeleton_draft("주제", items, outline=_OUTLINE)
    # 제목·맞춤 절·소절이 반영돼야 한다.
    assert "# 맞춤 제목" in md
    assert "## AI 글쓰기 효과" in md
    assert "### 자동 피드백" in md
    assert "### 한국(KR) 동향" in md


def test_build_messages_embeds_outline_instruction():
    items = _pool()
    draft._ensure_ids(items)
    _, user = draft.build_messages("주제", items, outline=_OUTLINE)
    assert "따라야 할 목차" in user
    assert "AI 글쓰기 효과" in user
    assert "2.1 한국(KR) 동향" in user
