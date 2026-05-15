# xnophon — 모노레포

두 개의 서브프로젝트를 포함한다:

1. **literature-review** (`src/literature_review/`) — 한·미 학술논문 비교 도구 (아래 본문)
2. **ai_trader** (`src/ai_trader/`) — AI 기반 한국·미국 주식 자동매매 (SL + RL + LLM). 상세: [`src/ai_trader/README.md`](src/ai_trader/README.md)

설치는 필요한 서브프로젝트의 extra를 지정한다:

```bash
pip install -e ".[dev]"                                       # literature-review만
pip install -e ".[ai-trader,ai-trader-data,ai-trader-ml,dev]" # ai_trader 포함
```

---

# literature-review — 한·미 학술논문 선행연구 비교 도구

OpenAlex API + Connected Papers + KCI 딥링크를 통합해 한국과 미국 학술논문을
주제별로 검색·비교하는 문헌검토(literature review) 도구. 세 가지 인터페이스를 제공:

1. **웹 UI** (`web/index.html`) — 브라우저 더블클릭으로 즉시 실행. 설치 불필요.
2. **CLI 챗봇** (`lr-chat`) — Claude Opus 4.7과 자연어 대화 또는 명령 REPL.
3. **일괄 비교 스크립트** (`lr-compare`) — 검색 결과를 Markdown 보고서로 저장.

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
│   └── sources/                  데이터 소스 어댑터
│       ├── openalex.py
│       └── (kci.py 추후)
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
