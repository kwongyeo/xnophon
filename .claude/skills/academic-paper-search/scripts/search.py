"""Multi-source academic paper search.

Sources:
    openalex   - OpenAlex (default, no auth)
    scholar    - Google Scholar (via scholarly or SerpAPI)
    arxiv      - arXiv API
    crossref   - Crossref REST API
    scienceon  - KISTI ScienceON (Korean, requires API key)
    consensus  - Consensus.app (requires CONSENSUS_API_KEY; prefer MCP in Claude)

Output is a JSON file with a normalized `papers` list plus per-source raw blobs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

import requests


def slugify(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", text).strip("-").lower()
    return s[:n] or "query"


# ---------- normalization ----------

def norm(*, source: str, title: str, authors: list[str], year: int | None,
         venue: str = "", doi: str = "", url: str = "", abstract: str = "",
         cited_by: int = 0, oa_pdf: str = "", country: str = "",
         language: str = "") -> dict:
    return {
        "source": source,
        "title": (title or "").strip(),
        "authors": [a for a in authors if a],
        "year": year,
        "venue": venue or "",
        "doi": (doi or "").replace("https://doi.org/", "").lower(),
        "url": url or "",
        "abstract": abstract or "",
        "cited_by": cited_by or 0,
        "oa_pdf": oa_pdf or "",
        "country": country or "",
        "language": language or "",
    }


# ---------- OpenAlex ----------

def search_openalex(query: str, limit: int, from_year: int | None,
                    country: str | None = None) -> list[dict]:
    try:
        from pyalex import Works, config
    except ImportError:
        print("[openalex] pyalex 미설치 — 건너뜀", file=sys.stderr)
        return []
    config.email = os.environ.get("OPENALEX_EMAIL", "anonymous@example.com")
    q = Works().search(query).sort(cited_by_count="desc")
    if from_year:
        q = q.filter(from_publication_date=f"{from_year}-01-01")
    if country:
        q = q.filter(authorships={"countries": country})
    try:
        raw = q.get(per_page=min(limit, 200))
    except Exception as e:
        print(f"[openalex] 오류: {e}", file=sys.stderr)
        return []
    out = []
    for w in raw[:limit]:
        loc = (w.get("primary_location") or {}) or {}
        oa = (w.get("best_oa_location") or {}) or {}
        countries = []
        for a in (w.get("authorships") or []):
            for c in (a.get("countries") or []):
                if c not in countries:
                    countries.append(c)
        out.append(norm(
            source="openalex",
            title=w.get("title") or "",
            authors=[(a.get("author") or {}).get("display_name", "")
                     for a in (w.get("authorships") or [])],
            year=w.get("publication_year"),
            venue=(loc.get("source") or {}).get("display_name", ""),
            doi=w.get("doi") or "",
            url=w.get("id") or "",
            abstract=_reconstruct_abstract(w.get("abstract_inverted_index")),
            cited_by=w.get("cited_by_count", 0),
            oa_pdf=oa.get("pdf_url") or "",
            country=",".join(countries),
            language=w.get("language") or "",
        ))
    return out


def _reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


# ---------- arXiv ----------

def search_arxiv(query: str, limit: int) -> list[dict]:
    try:
        import arxiv
    except ImportError:
        print("[arxiv] arxiv 미설치 — 건너뜀", file=sys.stderr)
        return []
    try:
        client = arxiv.Client()
        search = arxiv.Search(query=query, max_results=limit,
                              sort_by=arxiv.SortCriterion.Relevance)
        out = []
        for r in client.results(search):
            out.append(norm(
                source="arxiv",
                title=r.title,
                authors=[a.name for a in r.authors],
                year=r.published.year if r.published else None,
                venue="arXiv:" + r.get_short_id(),
                doi=r.doi or "",
                url=r.entry_id,
                abstract=r.summary,
                oa_pdf=r.pdf_url,
            ))
        return out
    except Exception as e:
        print(f"[arxiv] 오류: {e}", file=sys.stderr)
        return []


# ---------- Crossref ----------

def search_crossref(query: str, limit: int, from_year: int | None) -> list[dict]:
    params = {"query": query, "rows": min(limit, 100), "sort": "relevance"}
    if from_year:
        params["from-pub-date"] = f"{from_year}"
    try:
        r = requests.get("https://api.crossref.org/works", params=params, timeout=30)
        r.raise_for_status()
        items = r.json().get("message", {}).get("items", [])
    except Exception as e:
        print(f"[crossref] 오류: {e}", file=sys.stderr)
        return []
    out = []
    for it in items[:limit]:
        year = None
        for k in ("published-print", "published-online", "issued"):
            if it.get(k, {}).get("date-parts"):
                year = it[k]["date-parts"][0][0]
                break
        authors = [
            f"{a.get('given','')} {a.get('family','')}".strip()
            for a in (it.get("author") or [])
        ]
        out.append(norm(
            source="crossref",
            title=(it.get("title") or [""])[0],
            authors=authors,
            year=year,
            venue=(it.get("container-title") or [""])[0],
            doi=it.get("DOI", ""),
            url=it.get("URL", ""),
            abstract=re.sub(r"<[^>]+>", "", it.get("abstract", "")),
            cited_by=it.get("is-referenced-by-count", 0),
        ))
    return out


# ---------- Google Scholar ----------

def search_scholar(query: str, limit: int) -> list[dict]:
    serp_key = os.environ.get("SERPAPI_API_KEY")
    if serp_key:
        return _search_scholar_serpapi(query, limit, serp_key)
    return _search_scholar_scholarly(query, limit)


def _search_scholar_serpapi(query: str, limit: int, key: str) -> list[dict]:
    out = []
    try:
        for start in range(0, limit, 20):
            r = requests.get("https://serpapi.com/search.json", params={
                "engine": "google_scholar",
                "q": query,
                "start": start,
                "num": min(20, limit - start),
                "api_key": key,
            }, timeout=30)
            r.raise_for_status()
            for it in r.json().get("organic_results", []):
                pub = it.get("publication_info", {}) or {}
                summary = pub.get("summary", "")
                year_m = re.search(r"(19|20)\d{2}", summary)
                authors = [a.strip() for a in summary.split("-")[0].split(",")] \
                    if summary else []
                pdf = ""
                for res in it.get("resources") or []:
                    if res.get("file_format") == "PDF":
                        pdf = res.get("link", "")
                        break
                out.append(norm(
                    source="scholar",
                    title=it.get("title", ""),
                    authors=authors,
                    year=int(year_m.group(0)) if year_m else None,
                    venue=summary,
                    url=it.get("link", ""),
                    abstract=it.get("snippet", ""),
                    cited_by=(it.get("inline_links", {}).get("cited_by", {}) or {})
                              .get("total", 0),
                    oa_pdf=pdf,
                ))
                if len(out) >= limit:
                    return out
    except Exception as e:
        print(f"[scholar/serpapi] 오류: {e}", file=sys.stderr)
    return out


def _search_scholar_scholarly(query: str, limit: int) -> list[dict]:
    try:
        from scholarly import scholarly
    except ImportError:
        print("[scholar] scholarly 미설치, SERPAPI_API_KEY도 없음 — 건너뜀",
              file=sys.stderr)
        return []
    out = []
    try:
        it = scholarly.search_pubs(query)
        for _ in range(limit):
            try:
                pub = next(it)
            except StopIteration:
                break
            b = pub.get("bib", {}) or {}
            out.append(norm(
                source="scholar",
                title=b.get("title", ""),
                authors=b.get("author", []) if isinstance(b.get("author"), list)
                         else [b.get("author", "")],
                year=int(b.get("pub_year")) if str(b.get("pub_year","")).isdigit() else None,
                venue=b.get("venue", ""),
                url=pub.get("pub_url", ""),
                abstract=b.get("abstract", ""),
                cited_by=pub.get("num_citations", 0),
                oa_pdf=pub.get("eprint_url", ""),
            ))
    except Exception as e:
        print(f"[scholar/scholarly] 오류: {e} (Google rate-limit일 수 있음)",
              file=sys.stderr)
    return out


# ---------- ScienceON (KISTI, Korean papers) ----------

def search_scienceon(query: str, limit: int) -> list[dict]:
    api_key = os.environ.get("SCIENCEON_API_KEY")
    auth_key = os.environ.get("SCIENCEON_AUTH_KEY")
    if not (api_key and auth_key):
        print("[scienceon] SCIENCEON_API_KEY/SCIENCEON_AUTH_KEY 미설정 — 건너뜀",
              file=sys.stderr)
        return []
    try:
        url = "https://apigateway.kisti.re.kr/scienceon.rest/search"
        r = requests.get(url, params={
            "target": "ARTI",
            "searchQuery": json.dumps({"BI": query}, ensure_ascii=False),
            "displayCount": min(limit, 100),
            "apiKey": api_key,
            "authKey": auth_key,
        }, timeout=30)
        r.raise_for_status()
        records = r.json().get("response", {}).get("resultData", []) or []
    except Exception as e:
        print(f"[scienceon] 오류: {e}", file=sys.stderr)
        return []
    out = []
    for it in records[:limit]:
        out.append(norm(
            source="scienceon",
            title=it.get("Title", ""),
            authors=[a.strip() for a in (it.get("Author") or "").split(";") if a.strip()],
            year=int(it.get("Pubyear")) if str(it.get("Pubyear","")).isdigit() else None,
            venue=it.get("JournalName", ""),
            doi=it.get("DOI", ""),
            url=it.get("ContentURL", ""),
            abstract=it.get("Abstract", ""),
            country="KR",
            language="ko",
        ))
    return out


# ---------- Consensus (HTTP fallback; MCP is preferred) ----------

def search_consensus(query: str, limit: int) -> list[dict]:
    key = os.environ.get("CONSENSUS_API_KEY")
    if not key:
        print("[consensus] CONSENSUS_API_KEY 미설정 — 건너뜀 "
              "(Claude MCP 도구가 있으면 그걸 사용하세요)", file=sys.stderr)
        return []
    try:
        r = requests.get("https://api.consensus.app/v1/search", params={
            "query": query, "page_size": min(limit, 50),
        }, headers={"Authorization": f"Bearer {key}"}, timeout=30)
        r.raise_for_status()
        items = r.json().get("results", [])
    except Exception as e:
        print(f"[consensus] 오류: {e}", file=sys.stderr)
        return []
    out = []
    for it in items[:limit]:
        out.append(norm(
            source="consensus",
            title=it.get("title", ""),
            authors=it.get("authors", []) if isinstance(it.get("authors"), list) else [],
            year=it.get("year"),
            venue=it.get("journal", ""),
            doi=it.get("doi", ""),
            url=it.get("url", ""),
            abstract=it.get("abstract", ""),
            cited_by=it.get("citation_count", 0),
        ))
    return out


# ---------- driver ----------

SOURCES = {
    "openalex": lambda q, n, y: search_openalex(q, n, y),
    "openalex_kr": lambda q, n, y: search_openalex(q, n, y, country="KR"),
    "openalex_us": lambda q, n, y: search_openalex(q, n, y, country="US"),
    "arxiv": lambda q, n, y: search_arxiv(q, n),
    "crossref": lambda q, n, y: search_crossref(q, n, y),
    "scholar": lambda q, n, y: search_scholar(q, n),
    "scienceon": lambda q, n, y: search_scienceon(q, n),
    "consensus": lambda q, n, y: search_consensus(q, n),
}


def dedupe(papers: Iterable[dict]) -> list[dict]:
    seen_doi: dict[str, dict] = {}
    seen_title: dict[str, dict] = {}
    out: list[dict] = []
    for p in papers:
        key_doi = p["doi"].strip().lower()
        key_title = re.sub(r"\s+", " ", p["title"].strip().lower())
        if key_doi and key_doi in seen_doi:
            existing = seen_doi[key_doi]
            if not existing["oa_pdf"] and p["oa_pdf"]:
                existing["oa_pdf"] = p["oa_pdf"]
            existing.setdefault("also_seen_in", []).append(p["source"])
            continue
        if key_title and key_title in seen_title:
            existing = seen_title[key_title]
            if not existing["oa_pdf"] and p["oa_pdf"]:
                existing["oa_pdf"] = p["oa_pdf"]
            existing.setdefault("also_seen_in", []).append(p["source"])
            continue
        if key_doi:
            seen_doi[key_doi] = p
        if key_title:
            seen_title[key_title] = p
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description="Multi-source academic search")
    ap.add_argument("query")
    ap.add_argument("--sources", default="openalex,scholar,arxiv,crossref",
                    help="comma-separated; available: " + ",".join(SOURCES))
    ap.add_argument("--limit", type=int, default=20, help="per-source limit")
    ap.add_argument("--from-year", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    requested = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = [s for s in requested if s not in SOURCES]
    if unknown:
        print(f"unknown sources: {unknown}; valid: {list(SOURCES)}", file=sys.stderr)
        sys.exit(2)

    raw: dict[str, list[dict]] = {}
    for s in requested:
        print(f"[search] {s} ...", file=sys.stderr)
        raw[s] = SOURCES[s](args.query, args.limit, args.from_year)
        print(f"[search] {s}: {len(raw[s])} papers", file=sys.stderr)

    merged = []
    for s in requested:
        merged.extend(raw[s])
    deduped = dedupe(merged)
    deduped.sort(key=lambda p: (p.get("cited_by") or 0), reverse=True)

    out_path = Path(args.out or f"results/search_{slugify(args.query)}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "query": args.query,
        "sources": requested,
        "from_year": args.from_year,
        "papers": deduped,
        "raw": raw,
    }, ensure_ascii=False, indent=2))

    print(f"[search] done — {len(deduped)} unique papers → {out_path}")


if __name__ == "__main__":
    main()
