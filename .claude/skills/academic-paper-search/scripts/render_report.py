"""Render a KR/Overseas comparison Markdown report from search.py output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def is_korean(p: dict) -> bool:
    if "KR" in (p.get("country") or ""):
        return True
    if (p.get("language") or "").lower().startswith("ko"):
        return True
    if p.get("source") == "scienceon":
        return True
    venue = (p.get("venue") or "")
    if any("가" <= ch <= "힣" for ch in venue):
        return True
    return False


def table(rows: list[dict]) -> str:
    head = "| # | 제목 | 저자 | 연도 | 학술지 | 인용 | 출처 | OA | 링크 |\n"
    head += "|---|------|------|------|--------|------|------|----|------|\n"
    body = ""
    for i, r in enumerate(rows, 1):
        authors = ", ".join((r.get("authors") or [])[:3])
        oa = "PDF" if r.get("oa_pdf") else ""
        body += (f"| {i} | {r.get('title','')[:120]} | {authors} | "
                 f"{r.get('year','')} | {r.get('venue','')[:60]} | "
                 f"{r.get('cited_by',0)} | {r.get('source','')} | {oa} | "
                 f"[link]({r.get('url','')}) |\n")
    return head + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = json.loads(Path(args.input_json).read_text())
    papers = data.get("papers", [])
    kr = [p for p in papers if is_korean(p)]
    intl = [p for p in papers if not is_korean(p)]

    md = (
        f"# 문헌검토: {data.get('query','')}\n\n"
        f"소스: {', '.join(data.get('sources', []))}  ·  "
        f"총 {len(papers)}편 (국내 {len(kr)} / 해외 {len(intl)})\n\n"
        f"## 국내 (KR) — {len(kr)}편\n\n{table(kr) if kr else '_없음_'}\n\n"
        f"## 해외 — {len(intl)}편\n\n{table(intl) if intl else '_없음_'}\n"
    )
    out = Path(args.out or args.input_json.replace(".json", ".md"))
    out.write_text(md)
    print(f"saved → {out}")


if __name__ == "__main__":
    main()
