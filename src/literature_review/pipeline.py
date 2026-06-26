"""lr-run — 주제어 한 줄로 검색→인용 풀→초안→문서까지 한 번에.

개별 명령(lr-export · lr-draft · lr-build)을 손으로 이어 실행하는 대신,
하나의 오케스트레이터로 묶는다. 모든 산출물은 주제별 폴더
``results/<주제-slug>/`` 에 모인다.

    lr-run "large language model education" --per-country 30 --format pdf

단계:
    1) 검색   OpenAlex KR/US (+ KCI 한국어 보강) → 인용 풀
    2) 내보내기 citations.csl.json · citations.bib · paper_brief.md
    3) 초안   draft.md (ANTHROPIC_API_KEY 있으면 Claude, 없으면 골격)
    4) 변환   draft.<pdf|docx|...> (pandoc 있을 때만, --format 지정 시)

네트워크가 필요한 검색(1)과, 검색 결과만 있으면 동작하는 조립(2–4)을
분리해, 조립부(:func:`write_outputs`)는 오프라인 단위 테스트가 가능하다.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from literature_review import config
from literature_review.writing import build, draft, export


def write_outputs(
    topic: str,
    items: list[dict[str, Any]],
    out_dir: Path,
    *,
    use_llm: bool = False,
    model: str = config.DEFAULT_MODEL,
    formats: list[str] | None = None,
) -> dict[str, Any]:
    """인용 풀(items)로 내보내기→초안→(선택)변환을 수행하고 산출 경로를 돌려준다.

    네트워크 없이 동작(검색은 호출자 책임). use_llm=False면 골격 초안을 쓴다.
    formats가 있고 pandoc이 설치돼 있을 때만 문서 변환을 시도한다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 2) 내보내기 (citations.csl.json/.bib + paper_brief.md). id 키도 여기서 채워진다.
    paths = export.write_pool(topic, items, out_dir)

    # 3) 초안
    draft._ensure_ids(items)
    if use_llm and config.anthropic_key():
        draft_md = draft.generate_draft(topic, items, model=model)
    else:
        draft_md = draft.skeleton_draft(topic, items)
    draft_path = out_dir / "draft.md"
    draft_path.write_text(draft_md)

    # 4) 변환 (선택)
    built: list[Path] = []
    skipped_build = None
    if formats:
        if shutil.which("pandoc"):
            built = build.run(draft_path, out_dir, formats, paths["bib"])
        else:
            skipped_build = "pandoc 미설치 — 문서 변환을 건너뜀(draft.md 까지 생성)."

    return {
        "out_dir": out_dir,
        "citations": paths["csl"],
        "bibliography": paths["bib"],
        "brief": paths["brief"],
        "draft": draft_path,
        "built": built,
        "skipped_build": skipped_build,
        "count": len(items),
    }


def run(
    topic: str,
    *,
    from_year: int = config.DEFAULT_FROM_YEAR,
    per_country: int = config.DEFAULT_PER_COUNTRY,
    use_kci: bool = True,
    kci_count: int = config.DEFAULT_KCI_COUNT,
    use_llm: bool = True,
    model: str = config.DEFAULT_MODEL,
    formats: list[str] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """전체 파이프라인 실행(검색 포함). 검색은 OpenAlex/KCI 네트워크가 필요하다."""
    from literature_review.sources import openalex

    out = out_dir or config.topic_dir(topic)
    print(f"[1/4] 검색: '{topic}' (from {from_year}, {per_country}편/국가)")
    kr = openalex.search_csl(topic, "KR", from_year, per_country)
    us = openalex.search_csl(topic, "US", from_year, per_country)
    groups = [kr, us]

    if use_kci and config.kci_key():
        try:
            from literature_review.sources import kci

            kci_items = kci.search_csl(topic, count=kci_count)
            print(f"      KCI {len(kci_items)}편 병합")
            groups.append(kci_items)
        except Exception as e:  # noqa: BLE001 (보강 소스 실패는 비치명적)
            print(f"      KCI 병합 건너뜀: {e}")

    items = export.merge_pool(*groups)
    print(f"[2/4] 인용 풀 {len(items)}편 → 내보내기")
    print(f"[3/4] 초안 생성 ({'Claude ' + model if use_llm and config.anthropic_key() else '골격'})")
    if formats:
        print(f"[4/4] 문서 변환: {', '.join(formats)}")

    result = write_outputs(
        topic, items, out, use_llm=use_llm, model=model, formats=formats
    )
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="주제어 한 줄로 검색→인용 풀→초안→문서까지 한 번에 생성한다."
    )
    parser.add_argument("topic", help="논문 주제/검색어.")
    parser.add_argument("--from-year", type=int, default=config.DEFAULT_FROM_YEAR)
    parser.add_argument("--per-country", type=int, default=config.DEFAULT_PER_COUNTRY)
    parser.add_argument("--no-kci", action="store_true", help="KCI 보강 생략.")
    parser.add_argument("--skeleton", action="store_true", help="LLM 대신 골격 초안만 생성.")
    parser.add_argument("--model", default=config.DEFAULT_MODEL)
    parser.add_argument(
        "--format",
        default="",
        help="문서 변환 포맷(쉼표 구분): pdf,docx,latex,html. 생략 시 draft.md 까지만.",
    )
    parser.add_argument("--out-dir", default=None, help="출력 디렉터리(기본 results/<주제-slug>/).")
    args = parser.parse_args()

    formats = build.parse_formats(args.format) if args.format else None
    result = run(
        args.topic,
        from_year=args.from_year,
        per_country=args.per_country,
        use_kci=not args.no_kci,
        use_llm=not args.skeleton,
        model=args.model,
        formats=formats,
        out_dir=Path(args.out_dir) if args.out_dir else None,
    )

    print(f"\n완료: {result['out_dir']}/ (인용 {result['count']}편)")
    print(f"  - {result['citations']}")
    print(f"  - {result['bibliography']}")
    print(f"  - {result['brief']}")
    print(f"  - {result['draft']}")
    for p in result["built"]:
        print(f"  - {p}")
    if result["skipped_build"]:
        print(f"  ! {result['skipped_build']}")


if __name__ == "__main__":
    main()
