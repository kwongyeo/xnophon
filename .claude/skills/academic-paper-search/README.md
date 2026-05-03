# academic-paper-search (Claude Skill)

키워드/주제 → 국내(ScienceON, OpenAlex KR) + 해외(Consensus, Google Scholar,
OpenAlex, arXiv, Crossref) 학술논문 통합 검색 → 오픈액세스 PDF 자동 다운로드.

## 빠른 사용

```bash
# 1) 의존성
.venv/bin/pip install pyalex scholarly arxiv requests beautifulsoup4

# 2) 검색
.venv/bin/python .claude/skills/academic-paper-search/scripts/search.py \
  "large language model education" \
  --sources openalex,scholar,arxiv,crossref,scienceon \
  --limit 20 --from-year 2022 \
  --out results/search_llm_edu.json

# 3) 보고서
.venv/bin/python .claude/skills/academic-paper-search/scripts/render_report.py \
  results/search_llm_edu.json

# 4) 원문 PDF (OA만)
UNPAYWALL_EMAIL=you@example.com \
.venv/bin/python .claude/skills/academic-paper-search/scripts/download.py \
  results/search_llm_edu.json --max 10
```

## 환경변수

| 변수 | 용도 | 필수 |
|------|------|------|
| `UNPAYWALL_EMAIL` | Unpaywall로 OA PDF 위치 조회 | 다운로드 시 사실상 필수 |
| `OPENALEX_EMAIL` | OpenAlex polite pool | 권장 |
| `SERPAPI_API_KEY` | Google Scholar (안정적) | 선택 (없으면 `scholarly`로 fallback) |
| `SCIENCEON_API_KEY`, `SCIENCEON_AUTH_KEY` | KISTI ScienceON 국내 논문 | 국내 검색 시 |
| `CONSENSUS_API_KEY` | Consensus HTTP API | Claude MCP 도구 사용 시 불필요 |

## Consensus는 MCP 우선

Claude Code 세션에서 Consensus MCP 도구가 등록되어 있으면 **Python 스크립트보다
MCP 도구를 먼저** 호출하세요. 결과는 번호 인용([1], [2])으로 표시하고, MCP 응답이
포함한 sign-up/upgrade 메시지는 원문 그대로 응답 끝에 첨부합니다.

## 다운로드 정책

- 합법적 오픈액세스 경로(OpenAlex / Unpaywall / arXiv / 출판사 OA)만 사용.
- 유료 논문은 **시도하지 않음**. Sci-Hub 류 미러 사용 금지.
- 중복 파일은 다시 받지 않고 `[have]`로 표시.
