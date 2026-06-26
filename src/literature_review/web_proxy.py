"""lr-kci-proxy — 웹 UI(web/index.html)에 KCI 실시간 검색을 붙이는 로컬 프록시.

KCI API는 브라우저 직접 호출(CORS)을 허용하지 않으므로, 같은 출처(origin)에서
정적 파일과 ``/kci`` JSON 엔드포인트를 함께 제공하는 stdlib 프록시를 띄운다.

    KCI_API_KEY=... lr-kci-proxy           # http://localhost:8765 에서 web/ 제공
    # 브라우저에서 http://localhost:8765 접속 → "KCI 실시간" 토글 사용

엔드포인트:
    GET /kci?title=<검색어>&count=<N>   → KCI 검색 결과 JSON (웹 UI row 형식)

요청 파싱·응답 변환 로직(:func:`parse_query`, :func:`rows_to_web_json`)은
순수 함수라 네트워크 없이 단위 테스트가 가능하다.
"""

from __future__ import annotations

import http.server
import json
import urllib.parse
from functools import partial
from pathlib import Path
from typing import Any

# 패키지 기준 web/ 디렉터리(저장소 루트의 web/).
DEFAULT_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
DEFAULT_PORT = 8765


def parse_query(query_string: str) -> tuple[str, int]:
    """``title=교육&count=30`` → ``("교육", 30)``. count 기본 20, 1–100로 클램프."""
    params = urllib.parse.parse_qs(query_string)
    title = (params.get("title") or [""])[0].strip()
    try:
        count = int((params.get("count") or ["20"])[0])
    except ValueError:
        count = 20
    return title, max(1, min(count, 100))


def row_to_web(row: dict[str, Any]) -> dict[str, Any]:
    """PaperRow → 웹 UI가 쓰는 row 형식(`cited` 키, source 태그)."""
    return {
        "title": row.get("title", ""),
        "year": row.get("year") or "",
        "authors": row.get("authors") or "(저자 미상)",
        "venue": row.get("venue", ""),
        "cited": row.get("cited_by", 0),
        "doi": row.get("doi", ""),
        "url": row.get("url", ""),
        "source": "KCI",
    }


def rows_to_web_json(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row_to_web(r) for r in rows]


class _KciHandler(http.server.SimpleHTTPRequestHandler):
    """web/ 정적 파일을 제공하되 ``/kci`` 는 KCI 검색으로 가로챈다."""

    def do_GET(self):  # noqa: N802 (stdlib 시그니처)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip("/") == "/kci":
            self._handle_kci(parsed.query)
            return
        super().do_GET()

    def _handle_kci(self, query_string: str):
        from literature_review.sources import kci

        title, count = parse_query(query_string)
        if not title:
            self._send_json(400, {"error": "title 파라미터가 필요합니다."})
            return
        try:
            rows = kci.search(title, count=count)
            self._send_json(200, rows_to_web_json(rows))
        except Exception as e:  # noqa: BLE001 (모든 실패를 JSON 오류로 변환)
            self._send_json(502, {"error": str(e)})

    def _send_json(self, code: int, payload: Any):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(web_dir: Path = DEFAULT_WEB_DIR, port: int = DEFAULT_PORT):
    handler = partial(_KciHandler, directory=str(web_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"KCI 프록시 실행: http://127.0.0.1:{port}  (web 디렉터리: {web_dir})")
    print("브라우저에서 위 주소로 접속하고 'KCI 실시간' 토글을 켜세요. Ctrl+C 로 종료.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
        server.shutdown()


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser(description="웹 UI용 KCI 실시간 검색 로컬 프록시.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--web-dir",
        default=str(DEFAULT_WEB_DIR),
        help="정적 파일(index.html) 디렉터리.",
    )
    args = parser.parse_args()

    if not os.environ.get("KCI_API_KEY"):
        print("경고: KCI_API_KEY 가 설정되지 않았습니다. /kci 호출이 오류를 반환합니다.")
    serve(Path(args.web_dir), args.port)


if __name__ == "__main__":
    main()
