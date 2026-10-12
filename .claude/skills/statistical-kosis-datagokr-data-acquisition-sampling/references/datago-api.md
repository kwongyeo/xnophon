# 공공데이터포털(data.go.kr) 레퍼런스

KOSIS와 달리 data.go.kr은 **데이터셋마다 별도 API**이고, **API마다 활용신청 승인**이
있어야 호출된다. 인증키(일반 인증키)는 계정당 하나이며 승인된 모든 API에 공통으로 쓴다.

## 목차
1. MCP 서버 6종과 도구 — 1순위 경로
2. REST 직접 호출 — 위 6종 밖의 데이터셋이거나 MCP가 없을 때
3. 인증키: Encoding vs Decoding
4. 페이지네이션과 응답 양식
5. 오류 코드와 대응
6. 출처 표기

## 1. MCP 서버 6종 (Koomook/data-go-mcp-servers)

| 서버 | 데이터 | 도구 | 표본추출 단위로 쓸 때 |
|---|---|---|---|
| `data-go-nps-business-enrollment` | 국민연금 가입 사업장 | `search_business`, `get_business_detail`, `get_period_status` | 사업장 (층: 시도·업종·규모) |
| `data-go-nts-business-verification` | 국세청 사업자등록 상태/진위 | `check_business_status`, `validate_business`, `batch_validate_businesses` | 표본 사업자의 휴·폐업 검증 |
| `data-go-pps-narajangteo` | 조달청 나라장터 | `search_bid_announcements`, `get_bid_detail`, `search_successful_bids`, `search_contracts` | 입찰공고·계약 (층: 기관·공고종류·월) |
| `data-go-fsc-financial-info` | 금융위 기업 재무정보 | `search_company_financial_info`, `get_summary_financial_statement`, `get_balance_sheet`, `get_income_statement` | 기업 (층: 업종·자산규모) |
| `data-go-presidential-speeches` | 대통령기록관 연설문 | `search_speeches`, `list_speeches`, `get_recent_speeches` | 연설문 (층: 대통령·연도·분야) |
| `data-go-msds-chemical-info` | 화학물질 안전정보(MSDS) | `search_chemicals`, `get_complete_msds`, `get_chemical_section`, `get_chemical_properties`, `get_chemical_safety_summary`, `get_chemical_handling_info`, `get_chemical_regulatory_info` | 화학물질 |

여러 서버를 이어 쓰는 흔한 패턴: NPS로 사업장 모집단 수집 → 층화표본 추출 →
NTS `batch_validate_businesses`로 표본 사업자 상태 확인 → FSC로 재무 결합.

## 2. REST 직접 호출 (`scripts/acquire.py datago`)

data.go.kr 데이터셋 상세페이지의 **"요청주소(End Point)"와 오퍼레이션명**을 이어 URL을 만든다.

```bash
python scripts/acquire.py datago \
  --url "https://apis.data.go.kr/B552015/NpsBplcInfoInqireService/getBassInfoSearch" \
  --param wkpl_nm=삼성 \
  --size 100 --max-pages 50 \
  --out results/20260626-nps-samsung
```

- JSON 응답 파라미터는 API마다 이름이 다르다: `type=json`, `_type=json`, `dataType=JSON`,
  `resultType=json` 등. 상세페이지 요청변수 표를 보고 `--param`으로 넘긴다.
  지정하지 않아 XML이 와도 스크립트가 XML을 파싱한다.
- `api.odcloud.kr`(행정안전부 공공데이터 개방형 API, 파일데이터 API화)는 `--style odcloud`
  (페이지 파라미터 `page`/`perPage`, 응답 `data`/`totalCount`).
- POST 전용 API(예: 국세청 사업자 상태조회 `nts-businessman/v1/status`)는 MCP 도구를 쓴다.

## 3. 인증키: Encoding vs Decoding

마이페이지에 두 키가 나온다. 같은 키의 인코딩 여부만 다르다.

- **Decoding 키**(원문, `+ / =` 포함): 라이브러리가 URL 인코딩하게 둔다. 기본 권장.
- **Encoding 키**(`%2B` 등 포함): 이미 인코딩됨. 다시 인코딩하면 `%252B`가 되어
  `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`가 난다.

`acquire.py`는 키에 `%`가 있으면 Encoding 키로 보고 그대로 붙인다. 인증 오류가 나면
`.env`의 키를 다른 쪽으로 바꿔 본다. 승인 직후 1~2시간은 키 동기화 지연으로 같은
오류가 날 수 있다.

## 4. 페이지네이션과 응답 양식

| 양식 | 페이지 파라미터 | 항목 위치 | 전체 건수 |
|---|---|---|---|
| apis.data.go.kr (JSON) | `pageNo`, `numOfRows` | `response.body.items.item` (1건이면 dict) | `response.body.totalCount` |
| apis.data.go.kr (XML) | 동일 | `//item` | `//totalCount` |
| api.odcloud.kr | `page`, `perPage` | `data` | `totalCount` / `matchCount` |

종료 조건: 빈 페이지, 요청 크기보다 적은 페이지, 누적 ≥ totalCount, `--max-pages`.
`--max-pages`에서 멈추면 manifest의 `complete: false`로 남으므로, 모집단이 불완전하면
표본추출 전에 반드시 사용자에게 알린다 (불완전한 틀에서 뽑은 표본은 편향된다).

일일 트래픽 한도(개발계정 보통 1,000~10,000건/일)가 있으니, 모집단이 크면
`numOfRows`를 허용 최대치로 키워 호출 수를 줄인다.

## 5. 오류 코드와 대응

| 코드/메시지 | 의미 | 대응 |
|---|---|---|
| `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` (30) | 미등록 키·미승인 API | 활용신청 승인 확인, Encoding↔Decoding 교체, 승인 직후면 대기 |
| `LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR` (22) | 일일 트래픽 초과 | 다음 날 재개, 운영계정 신청 |
| `NO_OPENAPI_SERVICE_ERROR` (12) | 서비스 없음/URL 오류 | End Point·오퍼레이션명 확인 |
| `SERVICE_ACCESS_DENIED_ERROR` (20) | 접근 거부 | 활용신청 상태 확인 |
| `resultCode` 03 / NODATA | 결과 없음 | 검색 조건 완화 |
| `resultCode` 10 | 잘못된 파라미터 | 요청변수 표 재확인 |
| 프록시 403 | 실행 환경 egress 차단 | 우회 금지, 로컬에서 실행 |

## 6. 출처 표기

> 출처: 공공데이터포털(data.go.kr), 「데이터셋명」(제공기관), YYYY.MM.DD 수집

이용허락범위(공공누리 유형)는 데이터셋 상세페이지에 있다. 재배포·상업적 이용 계획이
있으면 유형을 확인해 보고서에 적는다.
