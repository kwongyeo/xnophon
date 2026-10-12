---
name: statistical-kosis-datagokr-data-acquisition-sampling
description: 국가통계포털(KOSIS)과 공공데이터포털(data.go.kr)에서 한국 공공·통계 데이터를 수집하고, 필요하면 확률표본(단순무작위·계통·층화·군집)을 뽑아 설계가중치와 추정치±표준오차까지 산출하는 통계 데이터 수집 스킬. MCP 서버(korean-stat, data-go-* 6종)를 우선 쓰고, 없으면 번들된 REST 스크립트로 대체하며, 키 보안·egress 차단 점검·40,000셀 분할·페이지네이션·출처 표기·manifest 기록까지 처리한다. 사용자가 "KOSIS에서 ~ 통계 가져와", "통계청 데이터 수집", "국가통계포털", "공공데이터포털", "data.go.kr API", "인구/고용/물가/사업체 통계 수집", "국민연금 사업장 데이터", "나라장터 입찰 데이터", "기업 재무정보 수집", "대통령 연설문 수집", "MSDS 데이터", "통계 데이터 표본추출", "층화추출", "샘플링해서 추정", "모집단에서 표본 뽑아줘", "공공데이터로 표본조사 설계" 등을 말하면 반드시 이 스킬을 사용할 것. 통계표 ID(DT_xxx)·orgId·serviceKey가 언급되거나, 한국 공공 통계를 연구·보고서·문헌검토의 근거 데이터로 모으려는 요청이면 KOSIS·data.go.kr을 명시하지 않아도 이 스킬을 쓴다. 해외 통계(World Bank, OECD, FRED), 주가·공시(DART), 학술논문 검색은 대상이 아니다.
---

# KOSIS · data.go.kr 통계 데이터 수집 및 표본추출

이 스킬은 "어디서 무엇을 가져올지 정하고 → 수집할 수 있는 환경인지 확인하고 → 작게 시험한 뒤 → 전부 가져오고 → (필요하면) 표본을 뽑아 추정하고 → 검증해서 출처와 함께 보고"하는 흐름을 담고 있다. 각 단계를 하는 이유는 공공 API가 실패하는 지점(키·승인·네트워크·셀 한도·페이지 누락)이 정해져 있고, 그걸 수집 전에 잡아야 틀린 데이터를 조용히 넘기지 않기 때문이다.

번들 리소스:
- `scripts/acquire.py` — 표준 라이브러리만 쓰는 CLI: `preflight`, `kosis-search`, `kosis-meta`, `kosis-data`, `datago`, `sample`, `estimate`. `--help`로 전체 옵션 확인.
- `references/kosis-api.md` — KOSIS MCP 도구, REST 파라미터, 분류(objL)·주기, 오류코드
- `references/datago-api.md` — data.go.kr MCP 6종과 도구, REST 호출, 키 인코딩, 오류코드
- `references/sampling-design.md` — 설계 선택, 표본 크기, 가중치·추정량, 검증 결과
- `references/setup.md` — `.mcp.json` 등록, 키 발급·취급, egress 차단 대응

스크립트 경로는 이 SKILL.md가 있는 디렉터리 기준이다. 산출물은 작업 디렉터리의 `results/<YYYYMMDD>-<slug>/`에 둔다 (리포지토리라면 `results/`가 gitignore인지 확인).

## 1단계 — 요청을 수집 사양으로 바꾸기

사용자 요청에서 다음을 뽑는다: **무엇**(지표·대상), **언제**(기간·주기), **어디/어떤 분류**(지역·성·연령·업종), **단위**, **용도**(보고서 수치인지, 분석용 원자료인지, 표본조사 틀인지). 빠진 것 중 결과를 크게 바꾸는 것만 묻고, 나머지는 합리적 기본값(가장 최근 10년, 전국+시도, 연 단위)을 쓰고 그 가정을 보고서에 적는다.

## 2단계 — 소스 라우팅

| 필요한 것 | 소스 | 이유 |
|---|---|---|
| 공표된 집계 통계 (인구, 고용률, 물가, GDP, 사업체 수 등) | KOSIS | 통계청·작성기관의 공식 집계표. 전수 또는 공식 표본조사 결과라 다시 표본추출하지 않는다 |
| 개별 레코드·행정자료 (사업장, 사업자 상태, 입찰공고, 기업 재무, 연설문, 화학물질) | data.go.kr | 레코드 단위라 모집단 틀·표본추출 대상이 된다 |
| 둘 다 | 둘 다 | 예: NPS 사업장 표본 추정치를 KOSIS 사업체 수 공표치와 대조 |

data.go.kr에서 MCP 6종(국민연금 사업장·국세청 사업자·나라장터·금융위 재무·대통령 연설·MSDS)에 없는 데이터셋은 `datago` REST 명령으로 직접 호출한다 (`references/datago-api.md` §2).

## 3단계 — 사전점검 (preflight)

수집 경로를 정하기 전에 실제로 닿는지 확인한다. 원격 실행 환경은 조직 egress 정책으로 이 도메인들을 막는 경우가 있고, 그러면 MCP 서버도 같이 막히기 때문이다.

```bash
python <skill-dir>/scripts/acquire.py preflight
```

결과에 따라 경로를 고른다:

1. **MCP 도구가 보이고 호스트 도달 가능** → MCP 경로 (A). 도구 이름은 `korean-stat` 서버의 `search_statistics` 등, `data-go-*` 서버의 `search_business` 등.
2. **MCP는 없지만 호스트 도달 가능, 키 있음** → REST 경로 (B), `acquire.py` 사용.
   - 위 둘이 안 되면 **세션에 연결된 다른 한국 데이터 커넥터**(예: PlayMCP `koreaStat-*`, `koreaProcurement-*`)를 ToolSearch로 찾아본다 (C). 사용자가 연결해 둔 커넥터는 승인된 도구라서 써도 되고, 이 환경의 egress를 우회하는 것이 아니다. 대신 이런 커넥터는 기간·지역·건수 범위가 제한된 경우가 많다(예: 최근 30일, 페이지당 15건, 일부 시도 누락). 그래서 작게 한 번 호출해 **요청 범위를 다 덮는지 먼저 확인**하고, 다 덮지 못하면 부분 데이터로 결론을 만들지 말고 무엇이 빠졌는지 보고한다. 결과를 쓸 때는 공식 원출처(KOSIS 통계표 ID 등)와 커넥터 경유라는 점을 함께 적는다.
3. **키 MISSING** → `references/setup.md`의 발급 경로를 안내한다. Claude는 사용자의 브라우저 로그인 세션에 접근할 수 없으므로 키를 대신 발급할 수 없다. 사용자가 키를 채팅에 붙여넣으면 값을 다시 출력하지 말고 `.env`에 기록한 뒤 재발급을 권한다.
4. **호스트 BLOCKED (프록시 403)이고 쓸 만한 커넥터도 없음** → 네트워크 차단 자체를 우회하지 않는다: 다른 프록시·터널, `HTTPS_PROXY` 해제, TLS 검증 끄기, 비공식 미러·스크래핑 사이트는 쓰지 않는다 (조직 정책 위반이고, 비공식 사본은 수치를 검증할 수 없다). 차단된 호스트를 보고하고, 사용자 PC에서 그대로 돌릴 수 있는 명령(아래 4~6단계)을 만들어 주며, Claude Code on the web이면 환경 설정의 허용 도메인에 해당 호스트를 추가하는 방법도 알려 준다. 표본설계·추정 단계는 사용자가 가진 CSV로 이 환경에서도 진행할 수 있다.

## 4단계 — 탐색과 시범조회

본 수집 전에 작게 한 번 요청해 키·승인·스키마·단위를 확인한다. 큰 요청이 실패하면 원인을 알기 어렵고, 성공해도 단위나 분류를 잘못 고른 걸 늦게 알게 된다.

**KOSIS**
- (A) `search_statistics` → `get_table_metadata` → `get_available_values` → `get_statistics_data`(최근 1시점)
- (B) `kosis-search "<키워드>"` → `kosis-meta --org-id 101 --tbl-id DT_xxx --type ITM` → `kosis-data … --latest 1 --out results/<slug>-pilot`

확인할 것: 분류 단계 수(objL1~n), 항목 ID와 단위(`UNIT_NM`), 기간 형식(`PRD_DE`), `DT`의 특수기호(`-`, `x`, `…`). 처음 쓰는 표의 분류 코드가 헷갈리면 KOSIS 통계표 화면의 [OpenAPI] 버튼이 만든 URL에서 파라미터를 옮긴다.

**data.go.kr**
- (A) 해당 서버의 검색 도구를 작은 조건으로 1회 호출
- (B) `datago --url <EndPoint/오퍼레이션> --param … --size 10 --max-pages 1 --out results/<slug>-pilot`

확인할 것: 인증 성공 여부(실패 시 활용신청 승인 → Encoding/Decoding 키 교체 순으로 점검), `totalCount`(모집단 크기), 필드 이름.

## 5단계 — 본 수집

```bash
# KOSIS: 40,000셀 초과(err 31)면 Y/H/Q/M 주기에서 기간을 자동 이분할해 병합
# (예시 값 — 실제 itmId·objL·주기는 4단계 시범조회 결과로 정한다)
python <skill-dir>/scripts/acquire.py kosis-data --org-id 101 --tbl-id DT_1B040A3 \
  --itm-id T20 --obj ALL --prd-se M --start 201401 --end 202312 --out results/20260626-pop-sigungu

# data.go.kr: totalCount까지 페이지 순회, 페이지 원본은 raw/에 (키 마스킹) 보존
python <skill-dir>/scripts/acquire.py datago --url "https://apis.data.go.kr/…/오퍼레이션" \
  --param 조건=값 --size 100 --max-pages 200 --out results/20260626-nps-frame
```

각 출력 디렉터리에는 `data.csv`(UTF-8 BOM, 엑셀 호환)와 `manifest.json`(엔드포인트·파라미터·수집 시각·행 수·SHA-256·출처 문구, 키 제외)이 생긴다. MCP 경로로 받았다면 같은 구조로 직접 저장하고 manifest를 남긴다. 나중에 같은 숫자를 다시 만들 수 있어야 보고서 수치를 방어할 수 있기 때문이다.

manifest의 `complete`가 `false`면(페이지 한도·트래픽 한도로 중단) 그 사실을 먼저 알린다. 불완전한 틀에서 뽑은 표본은 빠진 부분만큼 편향된다.

## 6단계 — 표본추출과 추정 (요청되었거나 필요할 때)

KOSIS 집계표는 이미 공표 통계라서, 거기서 "샘플"을 원하면 대개 미리보기(시범조회)나 하위집합 필터링이다. 이런 경우는 확률표본이 아니므로 가중치를 붙이지 않고 "표본"이라 부르지 않는다. 확률표본은 주로 data.go.kr 레코드 모집단에서 뽑는다. 설계 선택 기준과 표본 크기 공식은 `references/sampling-design.md`를 읽는다.

설계 전에 두 가지를 짚는다:
- **추정하려는 값이 이미 틀(모집단 파일)에 전부 있으면** 표본 추정보다 전수 합계가 정확하다. 그 사실을 먼저 말하고 전수값을 함께 제시한다. 이때 표본은 틀에 없는 항목(설문·현장확인·상세 API 조회)을 표본 단위에만 조사하거나 설계를 검증하는 용도다.
- **네이만 배분과 전수층 기준에는 조사 전에 알려진 보조변수**(전년도 값, 규모 변수 등)를 쓴다. 추정 대상 변수 자체로 배분하면 순환이 되고, 실제 조사에서는 그 값을 미리 알 수 없다. 적당한 보조변수가 없으면 비례배분이 안전한 기본값이다.

```bash
# 층화(시도) 300건: 비례배분 + 대규모 사업장 전수층, ID 정렬로 행 순서와 무관하게 재현
python <skill-dir>/scripts/acquire.py sample --input results/…/data.csv --method stratified \
  --strata 시도 --allocation proportional --n 300 --min-per-stratum 2 \
  --id-col 사업장ID --value 전년도_가입자수 --take-all-above 200 \
  --seed 20260626 --out results/…/sample.csv
# → sample.csv(_stratum, _weight 컬럼 추가) + sample.design.json(시드·입력 SHA-256·층별 N_h/n_h)

python <skill-dir>/scripts/acquire.py estimate --sample results/…/sample.csv \
  --design results/…/sample.design.json --value 가입자수
# → 총계·평균 추정치, 표준오차(fpc 반영), 95% 신뢰구간 (군집은 t(m−1))
```

재현성은 시드 + 입력 SHA-256 + `--id-col`로 보장한다 (design.json에 모두 기록됨). `--id-col` 없이 뽑으면 같은 시드여도 입력 행 순서가 바뀌는 순간 다른 표본이 나온다. 층에 n_h=1이면 분산을 추정할 수 없으니 `--min-per-stratum 2`를 쓴다. 값의 분포 꼬리가 길면(소수 대형 단위) 신뢰구간이 명목 95%보다 좁게 나오기 쉬우므로, `--take-all-above`로 대형 단위를 전수층에 넣고, 그래도 남는 한계는 보고서에 적는다.

## 7단계 — 검증

보고 전에 아래를 확인하고, 문제가 있으면 숨기지 않고 보고서에 적는다:
- **완전성**: 기대 시점·분류가 모두 있는지, data.go.kr은 수집 행 수 = `totalCount`인지
- **단위·값**: 단위(명/천명/%/백만원) 일관성, `DT` 특수기호를 결측으로 처리한 개수
- **중복**: 같은 키(시점×분류, 또는 레코드 ID) 중복 여부
- **교차검증**: KOSIS는 `verify_statistics` 또는 KOSIS 화면 공표치와 1~2개 셀 대조. 표본 추정치는 가능하면 KOSIS 공표 총계와 비교 (신뢰구간 안에 드는지)

## 8단계 — 보고

아래 구조로 보고한다. 수치마다 출처를 달아야 하는 이유는, 공공 통계는 개정·잠정치 갱신이 잦아 수집 시점 없이 숫자만 있으면 나중에 맞는지 확인할 수 없기 때문이다.

```markdown
# [주제] 데이터 수집 결과

## 요약
- 핵심 수치 2~4개 (단위, 시점 포함)

## 수집 사양
| 항목 | 내용 |
|---|---|
| 소스 / 통계표·API | KOSIS DT_xxx (orgId) 또는 data.go.kr 데이터셋명 |
| 기간·주기 / 분류 | 2014~2023, 연 / 시도 17개 |
| 수집 경로 | MCP(korean-stat) 또는 REST(acquire.py) |
| 행 수 / 완전성 | 1,870행 / complete |
| 파일 | results/…/data.csv, manifest.json |

## 표본설계와 추정 (해당 시)
- 틀 N, 방법·층·배분, n(층별 n_h), 시드
- 추정치 ± SE, 95% CI, 결측 수

## 검증과 한계
- 확인한 항목과 결과, 결측·잠정치·틀 누락 등

## 출처
- 출처: 통계청 KOSIS, 「통계표명」(DT_xxx), YYYY.MM.DD 수집
- 출처: 공공데이터포털(data.go.kr), 「데이터셋명」(제공기관), YYYY.MM.DD 수집
```

네트워크가 막혀 이 환경에서 수집하지 못했다면 그 사실을 보고서 맨 위에 쓰고, 수치를 지어내지 않는다. 대신 사용자 PC에서 실행할 명령과 기대되는 산출물을 적는다.

## 키·보안 원칙

- 키는 환경변수 또는 `.env`(`KOSIS_API_KEY`, `DATA_GO_KR_API_KEY`)에서만 읽는다. `acquire.py`는 URL·로그·raw 파일·manifest에서 키를 마스킹한다. 셸에서 직접 curl을 쓸 때도 키가 출력되지 않게 한다.
- `.env`가 git에서 제외되는지(`git check-ignore .env`) 확인하고, 키를 커밋·PR·이슈·보고서에 넣지 않는다.
