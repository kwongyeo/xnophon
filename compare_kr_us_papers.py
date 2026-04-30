"""한국과 미국의 연구논문을 OpenAlex에서 검색·비교하는 문헌검토 스크립트.

사용법:
    python compare_kr_us_papers.py "검색 주제" [--from-year 2020] [--per-country 25]

결과는 results/ 디렉터리에 다음 파일로 저장된다.
    - kr_papers.json / us_papers.json : 원본 메타데이터
    - literature_review.md            : 두 나라 논문을 나란히 비교한 마크다운 보고서
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyalex import Works, config

config.email = "kwongyeo@gmail.com"  # OpenAlex polite pool


def search_country(query: str, country_code: str, from_year: int, per_page: int):
    pager = (
        Works()
        .search(query)
        .filter(authorships={"countries": country_code})
        .filter(from_publication_date=f"{from_year}-01-01")
        .sort(cited_by_count="desc")
        .get(per_page=per_page)
    )
    return pager


def to_row(work: dict) -> dict:
    authors = ", ".join(
        a["author"]["display_name"]
        for a in (work.get("authorships") or [])[:3]
    )
    return {
        "title": work.get("title") or "(제목 없음)",
        "year": work.get("publication_year"),
        "authors": authors,
        "venue": (work.get("primary_location") or {}).get("source", {}).get("display_name", ""),
        "cited_by": work.get("cited_by_count", 0),
        "doi": work.get("doi") or "",
        "url": work.get("id", ""),
    }


def render_markdown(query: str, kr: list[dict], us: list[dict]) -> str:
    def table(rows):
        head = "| # | 제목 | 저자 | 연도 | 학술지 | 인용수 | 링크 |\n"
        head += "|---|------|------|------|--------|--------|------|\n"
        body = "".join(
            f"| {i+1} | {r['title']} | {r['authors']} | {r['year']} | {r['venue']} | {r['cited_by']} | [link]({r['url']}) |\n"
            for i, r in enumerate(rows)
        )
        return head + body

    return (
        f"# 선행연구(문헌검토): {query}\n\n"
        f"OpenAlex 데이터 기반, 인용수 내림차순.\n\n"
        f"## 한국 (KR) — {len(kr)}편\n\n{table(kr)}\n\n"
        f"## 미국 (US) — {len(us)}편\n\n{table(us)}\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="검색 주제 (예: 'large language model education')")
    parser.add_argument("--from-year", type=int, default=2020)
    parser.add_argument("--per-country", type=int, default=25)
    args = parser.parse_args()

    out = Path("results")
    out.mkdir(exist_ok=True)

    kr_raw = search_country(args.query, "KR", args.from_year, args.per_country)
    us_raw = search_country(args.query, "US", args.from_year, args.per_country)

    (out / "kr_papers.json").write_text(json.dumps(kr_raw, ensure_ascii=False, indent=2))
    (out / "us_papers.json").write_text(json.dumps(us_raw, ensure_ascii=False, indent=2))

    kr_rows = [to_row(w) for w in kr_raw]
    us_rows = [to_row(w) for w in us_raw]

    (out / "literature_review.md").write_text(render_markdown(args.query, kr_rows, us_rows))
    print(f"완료: results/literature_review.md (KR {len(kr_rows)} / US {len(us_rows)})")


if __name__ == "__main__":
    main()
