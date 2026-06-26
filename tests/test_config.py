"""config 의 slug/경로 유틸 단위 테스트(오프라인)."""

from __future__ import annotations

from pathlib import Path

from literature_review import config


def test_slugify_keeps_korean_and_replaces_separators():
    assert config.slugify("LLM in education") == "llm-in-education"
    assert config.slugify("대규모 언어모델 교육") == "대규모-언어모델-교육"
    assert config.slugify("  trailing/punct!!  ") == "trailing-punct"
    assert config.slugify("") == "untitled"


def test_slugify_truncates_long_input():
    assert len(config.slugify("x" * 200)) == 60


def test_topic_dir_under_results():
    d = config.topic_dir("LLM in education")
    assert d == Path("results") / "llm-in-education"


def test_load_prompt_reads_asset_file():
    # 실제 자산 파일이 존재하고 핵심 제약 문구를 담고 있어야 한다.
    text = config.load_prompt("draft_ko.md", "FALLBACK")
    assert "인용 위조 금지" in text
    assert text != "FALLBACK"


def test_load_prompt_falls_back_when_missing():
    assert config.load_prompt("does-not-exist.md", "FALLBACK") == "FALLBACK"
