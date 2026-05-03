"""Download open-access PDFs for papers in a search-result JSON file.

Resolution order per paper:
    1. paper["oa_pdf"]                                  (already known OA URL)
    2. arXiv pdf url derived from paper["url"] / venue
    3. Unpaywall API by DOI  → best_oa_location.url_for_pdf
    4. give up (paywalled / no OA)

Sci-Hub & similar mirrors are intentionally not used.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

UA = "academic-paper-search-skill/1.0 (mailto:%s)"


def safe_name(s: str, n: int = 80) -> str:
    s = re.sub(r"[^\w\-가-힣]+", "_", s).strip("_")
    return s[:n] or "paper"


def filename_for(p: dict) -> str:
    first = (p.get("authors") or ["unknown"])[0].split()[-1] if p.get("authors") else "unknown"
    year = p.get("year") or "n.d."
    title = safe_name(p.get("title", "paper"), 60)
    return f"{safe_name(first, 30)}_{year}_{title}.pdf"


def arxiv_pdf_url(p: dict) -> str | None:
    url = p.get("url", "")
    if "arxiv.org/abs/" in url:
        return url.replace("/abs/", "/pdf/") + ".pdf"
    venue = p.get("venue", "")
    m = re.search(r"arXiv:(\S+)", venue)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
    return None


def unpaywall_pdf(doi: str, email: str) -> str | None:
    if not doi:
        return None
    try:
        r = requests.get(f"https://api.unpaywall.org/v2/{doi}",
                         params={"email": email}, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None
    loc = data.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url")


def download(url: str, dest: Path, timeout: int = 60) -> bool:
    try:
        with requests.get(url, stream=True, timeout=timeout,
                          headers={"User-Agent": UA % "anonymous@example.com"},
                          allow_redirects=True) as r:
            ct = r.headers.get("content-type", "")
            if r.status_code != 200:
                return False
            if "pdf" not in ct.lower() and not url.lower().endswith(".pdf"):
                # non-PDF response (HTML landing page) — skip
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
            return dest.stat().st_size > 1024
    except Exception:
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        return False


def resolve_pdf_url(p: dict, email: str) -> tuple[str | None, str]:
    if p.get("oa_pdf"):
        return p["oa_pdf"], "oa_pdf"
    arx = arxiv_pdf_url(p)
    if arx:
        return arx, "arxiv"
    up = unpaywall_pdf(p.get("doi", ""), email)
    if up:
        return up, "unpaywall"
    return None, "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json", help="search.py 결과 JSON 경로")
    ap.add_argument("--out-dir", default="results/pdfs")
    ap.add_argument("--max", type=int, default=10, help="최대 다운로드 수")
    ap.add_argument("--email", default=os.environ.get("UNPAYWALL_EMAIL", ""))
    ap.add_argument("--sleep", type=float, default=1.0, help="요청 간 대기(초)")
    args = ap.parse_args()

    if not args.email:
        print("경고: UNPAYWALL_EMAIL 미설정 — Unpaywall fallback 비활성", file=sys.stderr)

    data = json.loads(Path(args.input_json).read_text())
    papers = data.get("papers", [])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log = []
    success = 0
    for p in papers[: args.max]:
        url, via = resolve_pdf_url(p, args.email or "anonymous@example.com")
        title = p.get("title", "")[:80]
        if not url:
            log.append({"title": title, "status": "no-oa", "via": via})
            print(f"[skip] {title} — OA 없음")
            continue
        dest = out_dir / filename_for(p)
        if dest.exists():
            log.append({"title": title, "status": "exists", "path": str(dest), "via": via})
            print(f"[have] {dest.name}")
            success += 1
            continue
        ok = download(url, dest)
        if ok:
            success += 1
            log.append({"title": title, "status": "ok", "path": str(dest),
                        "url": url, "via": via})
            print(f"[ok]   {dest.name}  ←  {urlparse(url).netloc} ({via})")
        else:
            log.append({"title": title, "status": "fail", "url": url, "via": via})
            print(f"[fail] {title} ({via})")
        time.sleep(args.sleep)

    log_path = out_dir / "_download_log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2))
    print(f"\n완료: {success}/{min(args.max, len(papers))} 성공  → {out_dir}")
    print(f"로그: {log_path}")


if __name__ == "__main__":
    main()
