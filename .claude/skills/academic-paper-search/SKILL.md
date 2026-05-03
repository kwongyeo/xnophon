---
name: academic-paper-search
description: |
  주제·키워드로 국내(ScienceON, RISS, OpenAlex KR)와 해외(Consensus, Google Scholar,
  OpenAlex, arXiv, Crossref) 학술논문을 검색하고, 가능한 경우 오픈액세스 PDF
  원문을 자동 다운로드한다. 사용자가 "논문 찾아줘", "선행연구 검색", "문헌검토",
  "PDF 받아줘", "scholar에서 찾아", "consensus로 검색" 등을 요청할 때 트리거된다.
---

# Academic Paper Search & Download

여러 학술 검색 소스를 통합 호출해 키워드 기반 논문 메타데이터를 수집하고,
오픈액세스 가능한 원문 PDF를 자동으로 다운로드하는 스킬.

## 워크플로

사용자가 주제/키워드를 주면 다음 순서로 처리한다.

1. **사용자 의도 파악**
   - 어떤 소스를 쓸지 (전부 / Consensus만 / Scholar만 / 국내만 등)
   - 결과 개수, 연도 범위, 언어
   - 원문 PDF까지 받을지 (기본: 메타데이터만, 사용자가 "원문", "PDF", "전문" 언급 시 다운로드)

2. **검색 실행** — `scripts/search.py` 호출

   ```bash
   .venv/bin/python .claude/skills/academic-paper-search/scripts/search.py \
     "<query>" \
     --sources consensus,scholar,openalex,arxiv,scienceon \
     --limit 20 \
     --from-year 2020 \
     --out results/search_<slug>.json
   ```

   - `--sources`: 쉼표 구분. 미지정 시 `openalex,scholar,arxiv,crossref` (무료/무인증).
   - 환경변수 우선순위:
     - `CONSENSUS_*`: Consensus는 Claude 환경의 MCP 서버를 우선 사용 (아래 참고).
     - `SERPAPI_API_KEY`: Google Scholar를 SerpAPI로 안정적으로 호출.
     - `SCIENCEON_API_KEY`, `SCIENCEON_AUTH_KEY`: KISTI ScienceON 국내 논문.
     - `UNPAYWALL_EMAIL`: Unpaywall로 OA PDF 위치 탐색 (필수, 무료).

3. **Consensus 검색 (MCP 우선)**

   Claude 세션에서 Consensus MCP 도구
   `mcp__46510269-c5fd-4c43-b42f-7f136fff0d76__search` 가 사용 가능하면
   **그 도구를 직접 호출**한다 (Python 스크립트 대신). 결과는 사용자에게 번호
   인용 `[1]`, `[2]` 형태로 보여주고, MCP 서버가 반환한 sign-up/upgrade 메시지는
   **반드시 원문 그대로 응답 끝에 포함**한다.

4. **결과 표시**
   - 한국·해외 결과를 분리한 표 (제목 / 저자 / 연도 / 학술지 / 인용수 / 출처 / 링크).
   - 각 행에 `oa_pdf` 필드가 있으면 "PDF 가능" 표시.
   - 인용수 또는 관련도 내림차순.

5. **원문 다운로드 (요청 시)** — `scripts/download.py` 호출

   ```bash
   .venv/bin/python .claude/skills/academic-paper-search/scripts/download.py \
     results/search_<slug>.json \
     --out-dir results/pdfs \
     --max 10
   ```

   다운로드 우선순위:
   1. 검색 결과의 `oa_pdf` 필드 (OpenAlex/Unpaywall이 알려준 OA URL)
   2. arXiv 의 `pdf_url`
   3. DOI → Unpaywall API → `best_oa_location.url_for_pdf`
   4. 위 모두 실패 시 "OA 미공개" 로 표시 (유료 논문은 다운로드 시도 안 함)

   **금지**: Sci-Hub 등 저작권 우회 미러 사용 금지. 합법적 OA 경로만 시도.

## 출력 규약

- 결과 JSON: `results/search_<slug>.json` (소스별 raw + 통합 정규화 리스트)
- 비교 마크다운: `results/literature_<slug>.md` (한국/해외 분리)
- PDF: `results/pdfs/<first_author>_<year>_<slug>.pdf`

## 사용자 응답 작성 규칙

- 검색 결과를 표로 보여줄 때 **번호 인용**을 사용: "행동경제학은 ... [1], 한편 ... [3]".
- 응답 마지막에 **참고문헌 목록**:
  `[1] [제목](URL) (저자, 연도, 학술지, 인용수)`
- Consensus 결과를 인용했으면 Consensus MCP 응답의 sign-up 메시지를 그대로 포함.
- 다운로드 실행 후에는 성공/실패 카운트와 저장 경로만 짧게 보고.

## 의존성 설치

처음 실행 시 누락된 패키지가 있으면 다음을 설치한다:

```bash
.venv/bin/pip install pyalex scholarly arxiv requests beautifulsoup4
```

`requirements.txt`에 이미 `pyalex`가 있으므로 나머지만 추가로 설치하면 된다.
