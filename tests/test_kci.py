"""sources.kci 의 XML 파서 단위 테스트(오프라인, 네트워크 불필요)."""

from __future__ import annotations

from literature_review.sources import kci
from literature_review.writing import citations

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaData lang="kor">
  <outputData>
    <result>
      <total>2</total>
      <record>
        <articleInfo article-id="ART001">
          <title-group>
            <article-title lang="kor">대규모 언어모델의 교육적 활용</article-title>
            <article-title lang="eng">LLM in Education</article-title>
          </title-group>
          <author-group>
            <author seq="1">홍길동</author>
            <author seq="2">김민수</author>
          </author-group>
          <journalInfo journal-id="J1">
            <journal-name lang="kor">교육공학연구</journal-name>
          </journalInfo>
          <pubInfo>
            <year>2022</year>
          </pubInfo>
          <citation-count>15</citation-count>
          <doi>10.1234/kci.2022.001</doi>
          <url>https://www.kci.go.kr/article/ART001</url>
        </articleInfo>
      </record>
      <record>
        <articleInfo article-id="ART002">
          <title-group>
            <article-title lang="kor">생성형 AI와 글쓰기 교육</article-title>
          </title-group>
          <author-group>
            <author seq="1">이순신</author>
          </author-group>
          <journalInfo>
            <journal-name lang="kor">국어교육</journal-name>
          </journalInfo>
          <pubInfo><year>2023</year></pubInfo>
        </articleInfo>
      </record>
    </result>
  </outputData>
</MetaData>
"""


def test_parse_search_xml_extracts_records():
    rows = kci.parse_search_xml(SAMPLE_XML)
    assert len(rows) == 2
    first = rows[0]
    assert first["title"] == "대규모 언어모델의 교육적 활용"
    assert first["authors"] == "홍길동, 김민수"
    assert first["year"] == 2022
    assert first["venue"] == "교육공학연구"
    assert first["cited_by"] == 15
    assert first["doi"] == "10.1234/kci.2022.001"
    assert first["url"] == "https://www.kci.go.kr/article/ART001"


def test_parse_handles_missing_optional_fields():
    rows = kci.parse_search_xml(SAMPLE_XML)
    second = rows[1]
    assert second["title"] == "생성형 AI와 글쓰기 교육"
    assert second["cited_by"] == 0  # citation-count 없음 → 0
    assert second["doi"] == ""
    assert second["year"] == 2023


def test_build_url_includes_required_params():
    url = kci._build_url("교육", count=30, page=2, key="SECRET")
    assert kci.KCI_BASE in url
    assert "apiCode=articleSearch" in url
    assert "key=SECRET" in url
    assert "displayCount=30" in url
    assert "page=2" in url


def test_kci_rows_convert_to_csl_with_kr_tag():
    rows = kci.parse_search_xml(SAMPLE_XML)
    item = citations.row_to_csl(rows[0], country="KR")
    assert item["custom"]["country"] == "KR"
    assert item["DOI"] == "10.1234/kci.2022.001"
    # 한국어 단일 토큰 저자 이름은 literal로 보존.
    assert item["author"][0] == {"literal": "홍길동"}
