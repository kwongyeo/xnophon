"""pipeline.write_outputs 의 오프라인 조립 테스트(검색·LLM·pandoc 불필요)."""

from __future__ import annotations

from literature_review import pipeline
from literature_review.writing import citations


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


def test_write_outputs_skeleton_path(tmp_path):
    out = tmp_path / "topic"
    result = pipeline.write_outputs("LLM 교육", _items(), out, use_llm=False, formats=None)

    # 산출 파일들이 모두 생성됐는지.
    assert result["citations"].exists()
    assert result["bibliography"].exists()
    assert result["brief"].exists()
    assert result["outline"].exists()
    assert (out / "outline.json").exists()
    assert result["draft"].exists()
    assert result["built"] == []
    assert result["count"] == 1
    assert result["sections"] >= 4

    # 목차 파일에 기본 절이 들어 있어야 한다.
    assert "## 목차" in result["outline"].read_text()

    # 골격 초안에 섹션과 인용 키가 들어 있어야 한다.
    draft_md = result["draft"].read_text()
    assert "## 서론" in draft_md
    assert "[kim2023large]" in draft_md

    # BibTeX에 엔트리가 있어야 한다.
    assert "@article{kim2023large," in result["bibliography"].read_text()


def test_write_outputs_skips_build_without_pandoc(tmp_path, monkeypatch):
    # pandoc이 없다고 가정 → 변환은 건너뛰고 draft.md 까지만.
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: None)
    result = pipeline.write_outputs(
        "LLM 교육", _items(), tmp_path / "t", use_llm=False, formats=["pdf"]
    )
    assert result["built"] == []
    assert result["skipped_build"] is not None
    assert result["draft"].exists()
