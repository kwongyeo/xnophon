# literature-review — 한·미 학술논문 선행연구 비교 도구

OpenAlex API + Connected Papers + KCI 딥링크를 통합해 한국과 미국 학술논문을
주제별로 검색·비교하는 문헌검토(literature review) 도구. 세 가지 인터페이스를 제공:

1. **웹 UI** (`web/index.html`) — 브라우저 더블클릭으로 즉시 실행. 설치 불필요.
2. **CLI 챗봇** (`lr-chat`) — Claude Opus 4.7과 자연어 대화 또는 명령 REPL.
3. **일괄 비교 스크립트** (`lr-compare`) — 검색 결과를 Markdown 보고서로 저장.
4. **논문 작성 연계** (`lr-export`) — 검색 결과를 표준 인용 포맷(CSL-JSON/BibTeX)과
   작성 브리프로 내보내, [opendraft](https://github.com/federicodeponte/opendraft)
   등 논문 작성 도구의 인용 풀로 바로 사용.

## 디렉터리 구조

```
literature-review/
├── README.md
├── pyproject.toml                패키지 메타 + 의존성 + 실행 진입점
├── .env.example                  API 키 템플릿
├── .gitignore
│
├── web/
│   └── index.html                정적 웹 UI (OpenAlex + CP + KCI 딥링크)
│
├── src/literature_review/
│   ├── __init__.py
│   ├── cli.py                    챗봇 진입점 (lr-chat)
│   ├── compare.py                일괄 비교 스크립트 (lr-compare)
│   ├── sources/                  데이터 소스 어댑터
│   │   ├── openalex.py
│   │   └── (kci.py 추후)
│   └── writing/                  논문 작성 도구 연계
│       ├── citations.py          CSL-JSON / BibTeX 변환기
│       └── export.py             인용 풀·브리프 내보내기 (lr-export)
│
├── docs/
│   └── kci-api-setup.md          KCI Open API 키 발급 가이드
│
├── tests/                        pytest 단위 테스트
└── results/                      검색 결과 출력 (gitignore)
```

## 설치

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

`-e .`는 개발 모드 설치로, 소스 수정이 즉시 반영된다. 끝나면 명령어 두 개가 PATH에 노출된다: `lr-chat`, `lr-compare`.

API 키를 사용하려면 `.env.example`을 `.env`로 복사하고 값을 채운다.

## 사용

### 1) 웹 UI (가장 간단)

```bash
# 파일 더블클릭 또는
xdg-open web/index.html       # Linux
open web/index.html           # macOS
start web\\index.html          # Windows
```

주제어 입력 → KR/US 비교 → 각 논문에서 Connected Papers·Semantic Scholar·Google Scholar·KCI 딥링크로 이동 → [저장] 버튼으로 Markdown 다운로드.

### 2) CLI 챗봇

```bash
.venv/bin/lr-chat
```

- `ANTHROPIC_API_KEY` 설정 시: **Claude Opus 4.7**이 자연어로 대화하며 OpenAlex 도구를 호출해 한·미 논문을 비교 요약.
- 미설정 시: 명령 기반 REPL (`/year`, `/count`, `/save`, `/help`, `/quit`).

### 3) 일괄 비교

```bash
.venv/bin/lr-compare "large language model education" --from-year 2022 --per-country 30
```

생성물(`results/`):
- `kr_papers.json`, `us_papers.json` — 원본 메타데이터
- `literature_review.md` — 인용수 내림차순 비교 표

### 4) 논문 작성 도구로 내보내기 (인용 풀 + 브리프)

검색·검증한 선행연구를 표준 인용 포맷으로 변환해, 논문 작성 자동화 도구
([opendraft](https://github.com/federicodeponte/opendraft) 등)의 **인용 풀**로 넘긴다.

```bash
# A) 새로 검색해서 내보내기 (저자 전체·초록·DOI 포함)
.venv/bin/lr-export "large language model education" --from-year 2022 --per-country 30

# B) 이미 만든 results/*.json 으로부터 (오프라인)
.venv/bin/lr-compare "large language model education"
.venv/bin/lr-export --from-results --topic "LLM in education"
```

생성물(`results/`):
- `citations.csl.json` — CSL-JSON 인용 풀 (Zotero·Pandoc·opendraft 공통 표준)
- `citations.bib` — BibTeX (LaTeX 작성용)
- `paper_brief.md` — 주제·검증된 출처 목록·작성 지시가 담긴 핸드오프 문서

## 논문 작성 자동화 파이프라인

`literature-review`(검색·비교)에서 논문 초안까지 이어지는 흐름:

```
lr-compare / lr-chat   →   lr-export   →   opendraft 등 작성 도구
  (검색·비교)              (인용 풀·브리프)     (초안·인용검증·PDF/Word/LaTeX)
```

`lr-export`가 만드는 인용 풀은 표준 포맷이라 opendraft 외에 Pandoc(`--bibliography
citations.bib`)이나 Zotero(CSL-JSON 가져오기)에도 그대로 쓸 수 있다. `paper_brief.md`는
"목록에 없는 문헌을 지어내지 말 것"(인용 위조 금지)을 명시해 LLM 작성 도구의
환각 인용을 억제한다.

## 통합된 데이터 소스

| 소스 | 통합 방식 | 비고 |
|---|---|---|
| OpenAlex | API 직접 호출 (CORS ✓) | 메인 검색, KR/US 결과 표시 |
| Connected Papers | 딥링크 | 인용 관계 그래프 (공개 검색 API 없음) |
| Semantic Scholar | 딥링크 | CP의 원본 데이터 소스 |
| Google Scholar | 딥링크 | 보조 검색 |
| KCI | 딥링크 | 한국어 논문 핵심 DB. **Open API 통합은 [docs/kci-api-setup.md](docs/kci-api-setup.md) 참조** |

## 라이선스

MIT
