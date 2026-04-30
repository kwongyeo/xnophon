# xnophon — 한·미 논문 문헌검토 도구

OpenAlex API([pyalex](https://github.com/J535D165/pyalex))를 사용해 한국(KR)과 미국(US)의 연구논문을 주제별로 검색하고 비교 마크다운 보고서를 생성한다.

## 설치

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 사용

### 1) 웹 브라우저 (가장 간단)

`index.html` 파일을 더블클릭해서 브라우저로 열면 끝. 백엔드·설치 불필요.
주제어 입력 → KR/US 논문 인용수 내림차순 비교 → 저장 버튼으로 Markdown 다운로드.

### 2) 챗봇 모드 (CLI)

```bash
.venv/bin/python chatbot.py
```

- `ANTHROPIC_API_KEY` 환경변수가 있으면 **Claude Opus 4.7**이 자연어로 대화하며 OpenAlex 도구를 호출해 한·미 논문을 검색·비교·요약한다.
- 없으면 명령 기반 간이 REPL로 동작한다 (`/year 2022`, `/count 20`, `/save 이름`, `/help`, `/quit`).

### 3) 일괄 비교 스크립트

```bash
.venv/bin/python compare_kr_us_papers.py "large language model education" --from-year 2022 --per-country 30
```

생성물(`results/` 폴더):
- `kr_papers.json`, `us_papers.json` — OpenAlex 원본 메타데이터
- `literature_review.md` — 인용수 내림차순 비교 표

## 옵션

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `query` | (필수) | 검색어 |
| `--from-year` | 2020 | 발행 연도 하한 |
| `--per-country` | 25 | 국가별 결과 수 |
