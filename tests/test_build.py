"""writing.build 의 Pandoc 명령 구성 단위 테스트(오프라인)."""

from __future__ import annotations

from pathlib import Path

from literature_review.writing import build


def test_parse_formats_filters_and_dedupes():
    assert build.parse_formats("pdf,docx,latex") == ["pdf", "docx", "latex"]
    assert build.parse_formats("PDF, pdf, bogus, html") == ["pdf", "html"]
    assert build.parse_formats("nope") == []


def test_build_command_with_bibliography():
    cmd = build.build_command(
        Path("results/draft.md"),
        Path("results/draft.pdf"),
        Path("results/citations.bib"),
    )
    assert cmd[0] == "pandoc"
    assert "results/draft.md" in cmd
    assert "-o" in cmd and "results/draft.pdf" in cmd
    assert "--citeproc" in cmd
    assert "--bibliography" in cmd
    assert "results/citations.bib" in cmd


def test_build_command_without_bibliography_omits_citeproc():
    cmd = build.build_command(Path("draft.md"), Path("draft.docx"), None)
    assert "--citeproc" not in cmd
    assert "--bibliography" not in cmd


def test_build_command_pdf_engine_only_for_pdf():
    pdf = build.build_command(Path("d.md"), Path("d.pdf"), None, pdf_engine="xelatex")
    assert "--pdf-engine=xelatex" in pdf
    docx = build.build_command(Path("d.md"), Path("d.docx"), None, pdf_engine="xelatex")
    assert not any(a.startswith("--pdf-engine") for a in docx)
