"""lr-export — 문헌검토 결과를 논문 작성 도구용 인용 풀로 내보낸다.

검색 결과(OpenAlex)를 표준 인용 포맷으로 변환해 ``results/``에 저장한다.

    - citations.csl.json   CSL-JSON 인용 풀 (Zotero·Pandoc·opendraft 등 공통)
    - citations.bib        BibTeX (LaTeX 작성용)
    - paper_brief.md       주제·출처 목록·작성 지시가 담긴 opendraft 핸드오프 문서

두 가지 입력 경로:

    # 1) 새로 검색해서 내보내기 (저자 전체·초록·DOI 포함, 네트워크 필요)
    lr-export "large language model education" --from-year 2022 --per-country 30

    # 2) lr-compare가 이미 만든 results/*.json 으로부터 (오프라인, 축약본)
    lr-export --from-results --topic "LLM in education"

이후 opendraft 등 작성 도구에 ``results/paper_brief.md``를 프롬프트로,
``results/citations.csl.json``(또는 .bib)을 인용 풀로 넘기면 된다.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from literature_review.writing import citations


def _dedupe_key(item: dict[str, Any]) -> str:
    return (
        item.get("DOI")
        or item.get("URL")
        or (item.get("title", "") or "").strip().lower()
    )


def merge_pool(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """여러 CSL 항목 그룹을 DOI/URL/제목 기준으로 중복 제거해 병합."""
    seen: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            key = _dedupe_key(item)
            if not key:
                continue
            existing = seen.get(key)
            # 더 많이 인용된(=메타데이터가 더 충실할 가능성) 항목을 우선.
            if existing is None or _cites(item) > _cites(existing):
                seen[key] = item
    return list(seen.values())


def _cites(item: dict[str, Any]) -> int:
    return (item.get("custom") or {}).get("cited_by_count", 0)


def _country(item: dict[str, Any]) -> str:
    return (item.get("custom") or {}).get("country", "")


def render_brief(topic: str, items: list[dict[str, Any]]) -> str:
    """opendraft 등에 넘길 작성 브리프(Markdown) 생성."""
    items_sorted = sorted(items, key=_cites, reverse=True)
    lines = [
        f"# 논문 작성 브리프: {topic}",
        "",
        "이 문서는 `literature-review`가 OpenAlex에서 수집·검증한 선행연구를",
        "논문 작성 도구(opendraft 등)에 넘기기 위한 핸드오프 자료다.",
        "",
        "## 작성 지시",
        "",
        f"- 주제: **{topic}**",
        "- 아래 **검증된 인용 풀(`citations.csl.json` / `citations.bib`)만** 근거로 사용하고,",
        "  목록에 없는 문헌을 새로 지어내지 말 것(인용 위조 금지).",
        "- 서론 → 선행연구(Related Work) → 본론 → 결론 구조로 작성.",
        "- 각 주장에는 `[저자(연도)]` 형식으로 인용을 부착하고 DOI를 보존할 것.",
        "- 한국(KR)·미국(US) 연구 동향의 차이를 선행연구 절에서 대비할 것.",
        "",
        f"## 인용 풀 ({len(items_sorted)}편, 인용수 내림차순)",
        "",
    ]
    for i, item in enumerate(items_sorted, 1):
        authors = "; ".join(
            a.get("literal") or f"{a.get('given','')} {a.get('family','')}".strip()
            for a in item.get("author", [])
        )
        year = "n.d."
        parts = (item.get("issued") or {}).get("date-parts") or [[]]
        if parts and parts[0]:
            year = str(parts[0][0])
        venue = item.get("container-title") or ""
        doi = item.get("DOI") or ""
        tag = _country(item)
        doi_str = f" doi:{doi}" if doi else ""
        tag_str = f" [{tag}]" if tag else ""
        lines.append(
            f"{i}. {authors} ({year}). *{item.get('title','')}*. "
            f"{venue}. 인용 {_cites(item)}{tag_str}{doi_str}"
        )
    lines.append("")
    lines.append("## opendraft 연계 예시")
    lines.append("")
    lines.append("```bash")
    lines.append("# https://github.com/federicodeponte/opendraft")
    lines.append("# paper_brief.md 를 주제/지시 프롬프트로, citations.bib 를 인용 풀로 사용")
    lines.append(f'opendraft --topic "{topic}" \\')
    lines.append("  --bibliography results/citations.bib \\")
    lines.append("  --export pdf,docx,latex")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def write_pool(topic: str, items: list[dict[str, Any]], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    bib = citations.csl_to_bibtex(items)  # id 필드를 채워주므로 csl 저장 전에 호출
    paths = {
        "csl": out_dir / "citations.csl.json",
        "bib": out_dir / "citations.bib",
        "brief": out_dir / "paper_brief.md",
    }
    paths["csl"].write_text(json.dumps(items, ensure_ascii=False, indent=2))
    paths["bib"].write_text(bib)
    paths["brief"].write_text(render_brief(topic, items))
    return paths


def _load_from_results(out_dir: Path) -> list[dict[str, Any]]:
    groups = []
    for fname, country in (("kr_papers.json", "KR"), ("us_papers.json", "US")):
        path = out_dir / fname
        if path.exists():
            rows = json.loads(path.read_text())
            groups.append([citations.row_to_csl(r, country=country) for r in rows])
    if not groups:
        raise SystemExit(
            f"{out_dir}/kr_papers.json 또는 us_papers.json 을 찾을 수 없습니다. "
            "먼저 lr-compare 를 실행하거나 검색어를 직접 지정하세요."
        )
    return merge_pool(*groups)


def main():
    parser = argparse.ArgumentParser(
        description="문헌검토 결과를 논문 작성 도구용 인용 풀(CSL-JSON/BibTeX)로 내보낸다."
    )
    parser.add_argument("query", nargs="?", help="검색 주제 (생략 시 --from-results 필요)")
    parser.add_argument("--from-year", type=int, default=2020)
    parser.add_argument("--per-country", type=int, default=25)
    parser.add_argument(
        "--from-results",
        action="store_true",
        help="새로 검색하지 않고 results/*.json(lr-compare 출력)에서 인용 풀을 만든다.",
    )
    parser.add_argument(
        "--topic",
        help="--from-results 모드에서 브리프에 표시할 주제 라벨(미지정 시 query 사용).",
    )
    parser.add_argument("--out-dir", default="results", help="출력 디렉터리(기본 results/).")
    parser.add_argument(
        "--no-kci",
        action="store_true",
        help="KCI_API_KEY가 있어도 KCI 한국어 논문 병합을 생략한다.",
    )
    parser.add_argument("--kci-count", type=int, default=20, help="KCI에서 가져올 논문 수.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    if args.from_results:
        topic = args.topic or args.query or "(주제 미지정)"
        items = _load_from_results(out_dir)
    else:
        if not args.query:
            parser.error("검색어(query)를 지정하거나 --from-results 를 사용하세요.")
        topic = args.topic or args.query
        from literature_review.sources import openalex

        kr = openalex.search_csl(args.query, "KR", args.from_year, args.per_country)
        us = openalex.search_csl(args.query, "US", args.from_year, args.per_country)
        groups = [kr, us]

        # KCI 한국어 논문 보강(키가 있고 --no-kci가 아닐 때만). 실패는 비치명적.
        if not args.no_kci and os.environ.get("KCI_API_KEY"):
            try:
                from literature_review.sources import kci

                kci_items = kci.search_csl(args.query, count=args.kci_count)
                print(f"  KCI에서 {len(kci_items)}편 병합")
                groups.append(kci_items)
            except Exception as e:  # noqa: BLE001 (보강 소스이므로 실패해도 진행)
                print(f"  KCI 병합 건너뜀: {e}")

        items = merge_pool(*groups)

    paths = write_pool(topic, items, out_dir)
    print(f"완료: 인용 {len(items)}편 내보냄")
    for label, path in paths.items():
        print(f"  - {path}")


if __name__ == "__main__":
    main()
