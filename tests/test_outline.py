"""writing.outline 순수 로직 단위 테스트(오프라인)."""

from __future__ import annotations

import pytest

from literature_review.writing import citations, outline


def _items():
    work = {
        "id": "https://openalex.org/W1",
        "title": "Large Language Models in Education",
        "publication_year": 2023,
        "doi": "https://doi.org/10.1/x",
        "cited_by_count": 42,
        "primary_location": {"source": {"display_name": "Journal of AI Ed"}},
        "authorships": [{"author": {"display_name": "Min Su Kim"}}],
    }
    return [citations.work_to_csl(work, country="US")]


def test_default_outline_shape():
    o = outline.default_outline("LLM 교육")
    assert o["title"] == "LLM 교육"
    headings = outline.section_headings(o)
    assert headings[0] == "서론"
    assert headings[-1] == "결론"
    assert any(h.startswith("선행연구") for h in headings)


def test_build_messages_includes_pool_and_schema_hint():
    system, user = outline.build_messages("LLM 교육", _items())
    assert "JSON" in system
    assert "LLM 교육" in user
    assert "Large Language Models in Education" in user  # 인용 풀 요약 포함


def test_parse_outline_response_plain_json():
    text = '{"title":"T","sections":[{"heading":"서론","subsections":[]},{"heading":"결론"}]}'
    o = outline.parse_outline_response(text, topic="주제")
    assert o["title"] == "T"
    assert outline.section_headings(o) == ["서론", "결론"]


def test_parse_outline_response_with_codefence_and_noise():
    text = "여기 목차입니다:\n```json\n{\"title\":\"T\",\"sections\":[{\"heading\":\"서론\"}]}\n```\n끝"
    o = outline.parse_outline_response(text)
    assert outline.section_headings(o) == ["서론"]


def test_parse_outline_response_rejects_empty_sections():
    with pytest.raises(ValueError):
        outline.parse_outline_response('{"title":"T","sections":[]}')


def test_normalize_drops_invalid_sections_and_trims():
    data = {"sections": [{"heading": "  서론  "}, {"no_heading": 1}, {"heading": ""}]}
    o = outline.normalize_outline(data, topic="주제")
    assert outline.section_headings(o) == ["서론"]
    assert o["title"] == "주제"  # title 누락 시 topic 사용


def test_outline_to_markdown_numbering():
    o = {
        "title": "제목",
        "sections": [
            {"heading": "서론", "subsections": []},
            {"heading": "선행연구", "subsections": ["한국(KR)", "미국(US)"]},
        ],
    }
    md = outline.outline_to_markdown(o)
    assert "# 제목" in md
    assert "1. 서론" in md
    assert "2. 선행연구" in md
    assert "2.1 한국(KR)" in md
    assert "2.2 미국(US)" in md
