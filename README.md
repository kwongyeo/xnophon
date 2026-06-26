# literature-review — 한·미 학술논문 선행연구 비교 도구

OpenAlex API + Connected Papers + KCI 딥링크를 통합해 한국과 미국 학술논문을
주제별로 검색·비교하는 문헌검토(literature review) 도구. 세 가지 인터페이스를 제공:

1. **웹 UI** (`web/index.html`) — 브라우저 더블클릭으로 즉시 실행. 설치 불필요.
2. **CLI 챗봇** (`lr-chat`) — Claude Opus 4.7과 자연어 대화 또는 명령 REPL.
3. **일괄 비교 스크립트** (`lr-compare`) — 검색 결과를 Markdown 보고서로 저장.
4. **논문 작성 연계** (`lr-export`) — 검색 결과를 표준 인용 포맷(CSL-JSON/BibTeX)과
   작성 브리프로 내보내, [opendraft](https://github.com/federicodeponte/opendraft)
   등 논문 작성 도구의 인용 풀로 바로 사용.
5. **초안 생성** (`lr-draft`) — 인용 풀에서 Claude(Opus)로 한국어 논문 초안을
   바로 생성. 풀에 있는 문헌만 인용(환각 인용 차단). 외부 도구 없이 자체 완결.
6. **문서 변환** (`lr-build`) — 초안 + BibTeX를 Pandoc으로 PDF/DOCX/LaTeX 변환.

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
│   ├── web_proxy.py              KCI 실시간 웹 프록시 (lr-kci-proxy)
│   ├── sources/                  데이터 소스 어댑터
│   │   ├── openalex.py
│   │   └── kci.py                KCI 한국어 논문 검색 (XML)
│   └── writing/                  논문 작성 도구 연계
│       ├── citations.py          CSL-JSON / BibTeX 변환기
│       ├── export.py             인용 풀·브리프 내보내기 (lr-export)
│       ├── draft.py              Claude 초안 생성 (lr-draft)
│       └── build.py              Pandoc 문서 변환 (lr-build)
│
├── scripts/
│   └── kci_proxy.py              lr-kci-proxy 실행 셸
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

**KCI 실시간 병합(선택):** KCI API는 브라우저 직접 호출(CORS)을 막으므로, 로컬 프록시를
띄우고 같은 주소로 접속하면 KCI 한국어 논문을 KR 목록에 실시간 병합할 수 있다.

```bash
KCI_API_KEY=<키> .venv/bin/lr-kci-proxy      # http://127.0.0.1:8765 에서 web/ 제공
# 브라우저로 위 주소 접속 → 'KCI 실시간' 토글 ON → 검색
```

프록시 없이 `file://`로 열면 토글이 무시되고(병합 실패 안내만 표시) 기존 딥링크는 그대로 동작한다.

### 2) CLI 챗봇

```bash
.venv/bin/lr-chat
```

- `ANTHROPIC_API_KEY` 설정 시: **Claude Opus 4.7**이 자연어로 대화하며 OpenAlex(`search_papers`)와
  KCI(`search_kci`) 도구를 호출해 한·미 논문을 비교 요약. `KCI_API_KEY`가 있으면 한국어 논문을
  자동으로 보강한다.
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

`KCI_API_KEY`가 설정돼 있으면 KCI 한국어 논문을 자동으로 KR 풀에 병합한다
(영문 DB가 약한 한국어 인문·사회과학 보강). 생략하려면 `--no-kci`.

생성물(`results/`):
- `citations.csl.json` — CSL-JSON 인용 풀 (Zotero·Pandoc·opendraft 공통 표준)
- `citations.bib` — BibTeX (LaTeX 작성용)
- `paper_brief.md` — 주제·검증된 출처 목록·작성 지시가 담긴 핸드오프 문서

### 5) 초안 생성 (Claude)

인용 풀에서 곧바로 한국어 논문 초안을 생성한다. 외부 도구 없이 자체 완결.

```bash
.venv/bin/lr-export "large language model education" --per-country 30
.venv/bin/lr-draft --topic "LLM을 활용한 교육"      # ANTHROPIC_API_KEY 필요

# API 키 없이 골격 초안만(섹션 틀 + References, 오프라인)
.venv/bin/lr-draft --topic "LLM을 활용한 교육" --skeleton
```

생성물: `results/draft.md` — 서론 → 선행연구(KR/US 대비) → 본론 → 결론 구조.
**인용 풀에 있는 문헌만** `[key]` 형식으로 인용하도록 강제해 환각 인용을 막는다.

### 6) 문서 변환 (Pandoc)

초안과 BibTeX를 합쳐 인용·참고문헌이 들어간 최종 문서를 만든다.

```bash
.venv/bin/lr-build --format pdf            # results/draft.md → results/draft.pdf
.venv/bin/lr-build --format docx,latex     # 여러 포맷 한 번에
.venv/bin/lr-build --format pdf --pdf-engine xelatex   # 한글 PDF 권장
```

[Pandoc](https://pandoc.org) 설치가 필요하다(PDF는 LaTeX 엔진도 필요). `citations.bib`가
있으면 `--citeproc`로 본문 `[key]` 인용을 자동 변환하고 참고문헌 목록을 생성한다.

## 논문 작성 자동화 파이프라인

`literature-review`(검색·비교)에서 최종 문서까지 이어지는 흐름:

```
lr-compare / lr-chat  →  lr-export  →  lr-draft  →  lr-build
 (검색·비교)            (인용 풀·브리프)  (Claude 초안)  (PDF/DOCX/LaTeX)
   + KCI 한국어 보강                  └ 또는 → opendraft 등 외부 도구
```

`lr-export`가 만드는 인용 풀은 표준 포맷이라 `lr-draft`(Claude) 외에 opendraft,
Pandoc(`--bibliography citations.bib`), Zotero(CSL-JSON 가져오기)에도 그대로 쓸 수
있다. `lr-draft`와 `paper_brief.md` 모두 "목록에 없는 문헌을 지어내지 말 것"(인용
위조 금지)을 명시해 LLM 작성 도구의 환각 인용을 억제한다.

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
