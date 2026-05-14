"""데이터 소스 어댑터.

각 소스(OpenAlex, KCI, Semantic Scholar 등)는 동일한 인터페이스로 한국·미국
논문 메타데이터를 반환한다. 새 소스를 추가하려면 search(query, country, ...)
를 노출하는 모듈을 이 패키지에 추가한다.
"""
