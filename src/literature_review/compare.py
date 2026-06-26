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

from literature_review import config
from literature_review.sources import openalex


def search_country(query: str, country_code: str, from_year: int, per_page: int):
    return openalex.search(query, country_code, from_year, per_page)


def to_row(work: dict) -> dict:
    return work


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
    parser.add_argument("--from-year", type=int, default=config.DEFAULT_FROM_YEAR)
    parser.add_argument("--per-country", type=int, default=config.DEFAULT_PER_COUNTRY)
    parser.add_argument(
        "--out-dir", default=None, help="출력 디렉터리(기본 results/<주제-slug>/)."
    )
    args = parser.parse_args()

    out = Path(args.out_dir) if args.out_dir else config.topic_dir(args.query)
    out.mkdir(parents=True, exist_ok=True)

    kr_raw = search_country(args.query, "KR", args.from_year, args.per_country)
    us_raw = search_country(args.query, "US", args.from_year, args.per_country)

    (out / "kr_papers.json").write_text(json.dumps(kr_raw, ensure_ascii=False, indent=2))
    (out / "us_papers.json").write_text(json.dumps(us_raw, ensure_ascii=False, indent=2))

    kr_rows = [to_row(w) for w in kr_raw]
    us_rows = [to_row(w) for w in us_raw]

    (out / "literature_review.md").write_text(render_markdown(args.query, kr_rows, us_rows))
    print(f"완료: {out / 'literature_review.md'} (KR {len(kr_rows)} / US {len(us_rows)})")


if __name__ == "__main__":
    main()
