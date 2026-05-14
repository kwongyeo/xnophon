# KCI Open API 키 발급·등록 가이드

KCI(한국학술지인용색인)는 한국연구재단이 운영하는 한국 학술지·논문 통합 색인이다.
영문 데이터베이스(OpenAlex, Semantic Scholar)가 잘 다루지 못하는 한국어 인문·사회과학
논문이 KCI에 풍부하게 색인되어 있어 한국 선행연구에 필수적이다.

## 1. 키 발급 절차

1. **회원가입** — https://www.kci.go.kr 우측 상단 [회원가입]
2. **OpenAPI 신청 페이지 이동** — https://open.kci.go.kr/po/openapi/openApiList.kci
3. **활용할 API 선택** (최소 `articleSearch` 필요)
   - `articleSearch` — 논문 검색 (제목·저자·키워드)
   - `articleDetail` — 논문 상세 정보 (초록, 참고문헌)
   - `journalInfo` — 학술지 정보
   - `citationInfo` — 인용 정보
4. **[OpenAPI 신청]** 클릭 → 활용 목적 작성. 예:
   > "한국·미국 학술논문 비교 문헌검토 도구 개발. 사용자가 입력한 주제어로 KCI 등재 한국어 논문을 검색해 OpenAlex 결과와 비교 표시하는 개인 연구용 도구."
5. **승인 대기** (보통 영업일 1–3일)
6. **마이페이지** → [OpenAPI 관리]에서 발급된 **인증키** 확인

## 2. 로컬 등록

프로젝트 루트의 `.env` 파일(없으면 `.env.example`을 복사해 생성)에 다음을 추가:

```bash
KCI_API_KEY=<발급받은_키>
```

`.env`는 `.gitignore`로 추적이 제외되므로 키가 저장소에 노출되지 않는다.

## 3. 호출 형식 (참고)

KCI API는 GET 방식, XML 응답이 기본이다.

```
https://open.kci.go.kr/po/openapi/openApiSearch.kci?apiCode=articleSearch&key=<API_KEY>&displayCount=20&page=1&title=<검색어>
```

| 파라미터 | 설명 |
|---|---|
| `apiCode` | 호출할 API 이름 (예: `articleSearch`) |
| `key` | 발급받은 인증키 |
| `displayCount` | 페이지당 결과 수 (최대 100) |
| `page` | 페이지 번호 (1부터 시작) |
| `title` | 제목 검색어 |
| `author` | 저자 검색어 |
| `affiliation` | 소속기관 검색어 |

응답은 XML이므로 Python에서는 `xml.etree.ElementTree` 또는 `xmltodict`으로 파싱한다.

## 4. CORS 제약

KCI API는 브라우저 직접 호출(`fetch`)을 허용하지 않을 가능성이 높다.
이 경우 `web/index.html`에서는 호출할 수 없고, Python 측(`src/literature_review/sources/kci.py`)
에서만 사용 가능하다. 브라우저 통합이 필요하면 다음 중 택일:

- **로컬 프록시**: Flask/FastAPI로 간단한 프록시(`/kci?title=...`)를 띄워 `index.html`이
  이를 호출하도록 한다.
- **Python CLI에서만 사용**: `lr-chat` / `lr-compare` 명령에서만 KCI를
  병합 검색 소스로 활용한다.

## 5. 이용 한도

신청 시 일/월 호출 한도가 부여된다. 일반적으로 일 1,000–10,000회 수준이며, 한도를
넘기면 일시 차단된다. 캐싱(예: `results/.cache/` 디렉터리)을 고려한다.

## 6. 키 발급 완료 후 진행할 작업

키를 알려주시면 `src/literature_review/sources/kci.py`에 다음을 구현해 통합한다:

- [ ] `search(query, page=1, count=20)` 함수 — 제목/키워드 검색
- [ ] XML → 공통 `PaperRow` 변환
- [ ] CLI(`lr-chat`)에 `search_kci` 도구 노출 (Claude Opus 4.7이 호출 가능)
- [ ] `compare.py`에 KCI 결과 별도 섹션 추가 (한국 결과 보강용)
- [ ] (선택) 로컬 프록시(`scripts/kci_proxy.py`)로 웹 UI 통합
