---
name: statistical-data-acquisition-sampling
description: 한국 광역·기초자치단체 통계(인구·고령·기초수급·세출결산 등)를 다년도 패널 데이터셋으로 수집·정제한다. 사용자가 "지자체 통계", "시도별 ○○ 2013~2024", "산업진흥비", "결산 분야별", "주민등록 인구", "노인인구", "기초생활수급자", 또는 패널 데이터셋/엑셀 생성 요청을 할 때 호출.
---

# statistical-data-acquisition-sampling — 통계 데이터 수집

본 알고리즘은 `stats_collect` 패키지(이 리포 `src/stats_collect/`)와 짝을 이룬다. 다음 규칙을 **그대로** 따른다.

## 절대 원칙

1. **숫자를 추정·생성하지 않는다.** 결산액·수급자수·인구 등 셀 값은 반드시 1차 출처에서 받은 원자료로만 채운다. 출처에서 받을 수 없는 셀은 비워 두고 결측률을 보고한다.
2. **출처(adapter)와 파이프라인(pipeline)을 분리한다.** 하나의 토픽 패널은 하나의 pipeline이, 각 출처 접근 로직은 `sources/<name>/`가 담당한다.
3. **3단 데이터 레이어를 지킨다.**  `data/raw/`(불변 원본) → `data/interim/`(정제 중간) → `data/processed/`(최종 패널). `data/`는 git 추적 대상이 아니며 `data/MANIFEST.csv`만 커밋한다.
4. **회계 범위 규칙** (지자체 재정 분석 시): **일반회계 + 특별회계** 통합, 기금 제외. 결산액 우선, 명목값으로 저장. 실질화는 분석 시점에 GDP 디플레이터로.
5. **행정구역 명칭은 2024 기준으로 통일.** 강원특별자치도(2023-06), 전북특별자치도(2024-01), 세종특별자치시(2012-07) 출범 반영.

## 1차 출처 매트릭스

| 자료 | 출처 | 어댑터 | 접근 |
|---|---|---|---|
| 세출 분야별 결산 (지자체 재정) | 지방재정365 (lofin.mois.go.kr) | `stats_collect.sources.lofin` | 사용자 다운로드 필요 |
| KOSIS 전반 (인구·고령·복지·경제) | kosis.kr/openapi | `stats_collect.sources.kosis` | `KOSIS_API_KEY` |
| 주민등록 월별 인구 | jumin.mois.go.kr | (예정) `sources.jumin` | 공개 |
| 공공데이터포털 OpenAPI | data.go.kr | (예정) `sources.data_go_kr` | 각 서비스별 키 |
| 자치단체 예결산서 PDF | 각 자치단체 홈페이지 | (예정) `sources.pdf` | 공개 |

## 실행 알고리즘

### 단계 0 — 요청 해석
사용자가 요청한 것을 다음 네 가지로 추출한다. 하나라도 모호하면 **단 하나의 명확한 질문**으로 되묻는다.
- **대상 레벨**: 광역(17) / 기초(226) / 둘 다 / 전국
- **연도 범위**: 명시 없으면 `YEARS_DEFAULT = 2013..2024`
- **변수 목록**: 각 변수의 이름·정의·단위
- **값 종류**: 결산 / 예산 / 재정자립도 등 파생지표

### 단계 1 — 변수별 1차 출처 매핑
각 변수를 위 매트릭스의 어댑터 하나에 할당한다. 하나의 변수를 여러 출처에서 받을 수 있을 때는 **1차 출처 > 2차 > …** 서열(README의 자료출처 블록)을 따른다.

### 단계 2 — 접근 가능성 확인
- lofin 자료가 필요한데 `data/raw/lofin/` 가 비어 있으면: 사용자에게 다운로드 지시(연도·회계·분야 조건)만 안내하고, 숫자를 임의로 채우지 않는다.
- KOSIS 자료가 필요한데 `KOSIS_API_KEY` 가 없으면: 발급 안내 후 중단.
- 접근 불가 시, 템플릿(빈 패널)만 생성해 사용자가 수기로 채울 수 있게 한다 (`industry-promotion --template-only`).

### 단계 3 — 코드·식별자 검증
KOSIS·data.go.kr 는 운영상 `tbl_id`/`itm_id`/`obj_l2` 가 바뀐다. **빌드 전** 반드시 `stats-collect kosis-discover --keyword "..."` 로 현행 식별자를 확인하고, 결과를 `configs/sources/kosis_vars.yaml` 에 반영한다.

### 단계 4 — 설정 파일 작성·갱신
변수·식별자는 `configs/sources/<source>.yaml` 와 `configs/pipelines/<topic>.yaml` 에만 둔다. **코드에 하드코딩하지 않는다.** 새 변수 추가 시 코드 변경 없이 config 만 수정하면 되도록.

### 단계 5 — 파이프라인 실행
```
stats-collect industry-promotion --raw-dir data/raw/lofin \
    --out data/processed/<topic>_<asof>.xlsx
stats-collect kosis-population --config configs/sources/kosis_vars.yaml \
    --out data/processed/<topic>_<asof>.xlsx
```
결과 xlsx는 `panel` 시트 (long-format) + `README` 시트 (대상·정의·회계 범위·출처·주의사항)를 포함해야 한다.

### 단계 6 — 품질 보고
빌드 후 다음을 보고한다:
- 변수별 결측률(%) — 결측률 20% 이상이면 사용자에게 알리고 보강 출처 제안
- 행정구역 변경에 걸치는 셀 (강원·전북 특별자치도 출범 이전 명목만 사용했는지)
- 명목·결산·회계범위 가정이 분석 목적에 맞는지 재확인

### 단계 7 — 파생 변수 생성
결측 없는 셀만을 대상으로:
- GDP 디플레이터 적용 실질화 → `*_real_<base>` 컬럼
- 1인당 지표 → `pop_total`로 나눔
파생 수식은 가능하면 엑셀 셀 수식으로 저장(사용자가 원값을 수정했을 때 자동 갱신).

## 산출물 레이아웃

```
data/
  raw/<source>/<year>/...     ← 불변, git 제외
  interim/<topic>/*.parquet   ← 정제 중간, git 제외
  processed/<topic>_<asof>.xlsx  ← 최종 패널, git 제외
  MANIFEST.csv                ← raw 파일 추적, git 추적
configs/
  sources/<source>.yaml       ← 변수·식별자 정의
  pipelines/<topic>.yaml      ← 토픽별 범위·회계·단위 명세
```

## 금지 사항

- 결산액·인구·수급자수 등 셀 값을 LLM이 추정해 채우지 않는다.
- 어댑터(sources) 코드가 토픽별 분기를 하지 않는다 — 분기는 pipelines 에서.
- `data/raw/` 안의 파일을 수정하지 않는다 — 재현성 파괴.
- 하나의 pipeline이 두 출처의 raw를 동시에 읽지 않는다 — 각 출처는 자신의 어댑터를 거쳐야 한다.
- `-u` 없이 git push 하지 않는다. 숫자 생성 커밋을 만들지 않는다.

## 사용자 상호작용 패턴

- 숫자가 비어 있는 패널을 제출할 때는 왜 비어 있는지(미접근/미승인/API 키 없음) 한 줄로 명시한다.
- "진행!" 같은 짧은 승인에도 **접근 불가**가 가로막으면 자동으로 템플릿 모드로 전환하고, 사용자에게 다음 액션(파일 업로드 or 키 발급)을 1~2줄로 요청한다.
- 추천할 때는 1차 출처(가장 공식), 접근 비용(API/수기), 갱신주기, 결측 가능성 네 가지를 묶어 제시한다.

## 확장 지점

새 출처를 더할 때는:
1. `src/stats_collect/sources/<name>/__init__.py` + `client.py`(또는 `parser.py`)
2. `configs/sources/<name>.yaml` (식별자 카탈로그)
3. `docs/SOURCES.md` 표에 한 줄 추가
4. 새 pipeline이 필요하면 `src/stats_collect/pipelines/<topic>.py` + `configs/pipelines/<topic>.yaml` + `cli.py` 서브커맨드

새 변수만 더할 때는 config YAML 수정만으로 충분해야 한다 (코드 변경 금지).

## 참고 문서

- `docs/SOURCES.md` — 출처별 URL·인증·갱신주기·회계 규칙
- `docs/CODEBOOK.md` — 변수 사전 (정의·단위·KOSIS 식별자)
- `configs/sources/kosis_vars.yaml` — KOSIS 기본 변수 3종
- `configs/pipelines/industry_promotion.yaml` — 산업진흥비 패널 명세
