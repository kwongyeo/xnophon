"""web_proxy 의 순수 헬퍼 단위 테스트(오프라인, 서버 미기동)."""

from __future__ import annotations

from literature_review import web_proxy


def test_parse_query_defaults_and_clamp():
    assert web_proxy.parse_query("title=교육") == ("교육", 20)
    assert web_proxy.parse_query("title=교육&count=30") == ("교육", 30)
    assert web_proxy.parse_query("title=x&count=999") == ("x", 100)  # 상한 클램프
    assert web_proxy.parse_query("title=x&count=0") == ("x", 1)      # 하한 클램프
    assert web_proxy.parse_query("title=x&count=abc") == ("x", 20)   # 잘못된 값 → 기본
    assert web_proxy.parse_query("") == ("", 20)


def test_row_to_web_maps_paperrow_to_ui_shape():
    row = {
        "title": "한국어 LLM 연구",
        "year": 2022,
        "authors": "홍길동",
        "venue": "교육공학연구",
        "cited_by": 15,
        "doi": "10.1/x",
        "url": "https://www.kci.go.kr/article/1",
    }
    web = web_proxy.row_to_web(row)
    assert web["cited"] == 15           # cited_by → cited
    assert web["source"] == "KCI"       # 출처 태그 부착
    assert web["title"] == "한국어 LLM 연구"
    assert web["doi"] == "10.1/x"


def test_row_to_web_handles_missing_fields():
    web = web_proxy.row_to_web({})
    assert web["authors"] == "(저자 미상)"
    assert web["cited"] == 0
    assert web["year"] == ""


def test_rows_to_web_json_maps_all():
    rows = [{"title": "a", "cited_by": 1}, {"title": "b", "cited_by": 2}]
    out = web_proxy.rows_to_web_json(rows)
    assert [r["cited"] for r in out] == [1, 2]
    assert all(r["source"] == "KCI" for r in out)
