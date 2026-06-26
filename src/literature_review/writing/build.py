"""lr-build — 초안(draft.md)을 Pandoc으로 PDF/DOCX/LaTeX로 변환한다.

`lr-draft`가 만든 `results/draft.md`와 `lr-export`가 만든 `results/citations.bib`를
Pandoc의 citeproc로 결합해 인용·참고문헌이 포함된 최종 문서를 만든다.

    lr-build --format pdf            # results/draft.md → results/draft.pdf
    lr-build --format docx,latex     # 여러 포맷 한 번에

Pandoc(및 PDF의 경우 LaTeX 엔진)이 설치돼 있어야 한다. 명령 구성 로직
(:func:`build_command`)은 순수 함수라 네트워크/설치 없이 단위 테스트가 가능하다.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

# 포맷별 출력 확장자.
FORMAT_EXT = {
    "pdf": "pdf",
    "docx": "docx",
    "latex": "tex",
    "html": "html",
}


def build_command(
    draft: Path,
    out: Path,
    bibliography: Path | None = None,
    *,
    pdf_engine: str | None = None,
) -> list[str]:
    """Pandoc 호출 인자 목록을 구성한다(순수 함수)."""
    cmd = [
        "pandoc",
        str(draft),
        "--from",
        "markdown",
        "--standalone",
        "-o",
        str(out),
    ]
    if bibliography is not None:
        cmd += ["--citeproc", "--bibliography", str(bibliography)]
    if out.suffix == ".pdf" and pdf_engine:
        cmd += [f"--pdf-engine={pdf_engine}"]
    return cmd


def parse_formats(value: str) -> list[str]:
    """'pdf,docx' → ['pdf', 'docx'] (유효 포맷만, 중복 제거, 순서 보존)."""
    seen: list[str] = []
    for f in value.split(","):
        f = f.strip().lower()
        if f and f in FORMAT_EXT and f not in seen:
            seen.append(f)
    return seen


def run(
    draft: Path,
    out_dir: Path,
    formats: list[str],
    bibliography: Path | None,
    *,
    pdf_engine: str | None = None,
) -> list[Path]:
    """각 포맷으로 변환을 실행하고 생성된 파일 경로 목록을 반환."""
    if shutil.which("pandoc") is None:
        raise SystemExit(
            "pandoc 가 설치돼 있지 않습니다. https://pandoc.org/installing.html 참고.\n"
            "  (예: apt-get install pandoc / brew install pandoc)"
        )
    produced = []
    for fmt in formats:
        out = out_dir / f"{draft.stem}.{FORMAT_EXT[fmt]}"
        cmd = build_command(draft, out, bibliography, pdf_engine=pdf_engine)
        print(f"  $ {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        produced.append(out)
    return produced


def main():
    parser = argparse.ArgumentParser(
        description="초안(draft.md)을 Pandoc으로 PDF/DOCX/LaTeX로 변환한다."
    )
    parser.add_argument("--draft", default="results/draft.md", help="입력 초안 Markdown.")
    parser.add_argument(
        "--bibliography",
        default="results/citations.bib",
        help="인용 풀(.bib). 존재하면 citeproc로 참고문헌을 생성한다.",
    )
    parser.add_argument(
        "--format",
        default="pdf",
        help="출력 포맷(쉼표 구분): pdf,docx,latex,html.",
    )
    parser.add_argument("--out-dir", default="results", help="출력 디렉터리.")
    parser.add_argument(
        "--pdf-engine",
        default=None,
        help="PDF 변환에 쓸 LaTeX 엔진(예: xelatex). 한글 PDF는 xelatex 권장.",
    )
    args = parser.parse_args()

    draft = Path(args.draft)
    if not draft.exists():
        raise SystemExit(f"{draft} 를 찾을 수 없습니다. 먼저 lr-draft 로 초안을 생성하세요.")

    formats = parse_formats(args.format)
    if not formats:
        raise SystemExit(f"유효한 포맷이 없습니다: {args.format} (지원: {', '.join(FORMAT_EXT)})")

    bib = Path(args.bibliography)
    bibliography = bib if bib.exists() else None
    if bibliography is None:
        print(f"참고: {bib} 가 없어 인용 처리 없이 변환합니다.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    produced = run(draft, out_dir, formats, bibliography, pdf_engine=args.pdf_engine)
    print("완료:")
    for p in produced:
        print(f"  - {p}")


if __name__ == "__main__":
    main()
