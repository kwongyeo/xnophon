# KOSIS OpenAPI 레퍼런스

통계표를 찾고, 그 구조를 파악하고, 데이터를 가져오는 데 필요한 내용만 정리했다.
파라미터 이름은 KOSIS 개발가이드(https://kosis.kr/openapi/ → 개발가이드) 기준이다.
처음 쓰는 통계표라면 본 수집 전에 반드시 소량 시범조회로 응답 구조를 확인한다.

## 목차
1. MCP 도구 (korean-stat) — 1순위 경로
2. REST 엔드포인트 — MCP를 못 쓸 때
3. 통계표 식별자와 분류 파라미터
4. 수록주기와 기간 형식
5. 오류 코드와 대응
6. 출처 표기

## 1. MCP 도구 (korean-stat)

| 단계 | 도구 | 용도 |
|---|---|---|
| 탐색 | `search_statistics` | 키워드로 통계표 검색 → orgId/tblId 확보 |
| 탐색 | `browse_categories` | 주제·기관별 목록 브라우징 |
| 구조 | `get_table_metadata` | 분류(objL)·항목(itmId)·단위·수록기간 |
| 구조 | `get_available_values` | 분류별 선택 가능 코드값 (예: 시도 코드) |
| 조회 | `get_statistics_data` | 데이터 조회. 요약만 반환하고 원본은 파일로 저장 → `data_id` |
| 가공 | `filter_statistics` / `aggregate_statistics` | 저장된 데이터 필터·집계 |
| 원본 | `list_stored_data` / `read_stored_data` | 저장 파일 목록·청크 읽기 |
| 검증 | `verify_statistics` | 조회값 교차검증 |

권장 순서: `search_statistics` → `get_table_metadata` → `get_available_values` →
`get_statistics_data`(시범: 최근 1시점) → `get_statistics_data`(본 수집) →
`read_stored_data`로 원본을 받아 `results/`에 CSV 저장.

## 2. REST 엔드포인트 (scripts/acquire.py가 감싼 것)

기본 URL `https://kosis.kr/openapi/`, 공통 파라미터 `apiKey`, `format=json`, `jsonVD=Y`.
(`jsonVD=Y`가 빠지면 따옴표 없는 key의 비표준 JSON이 와서 파싱이 깨진다.)

| 용도 | 경로 | 핵심 파라미터 | 스크립트 |
|---|---|---|---|
| 통합검색 | `statisticsSearch.do?method=getList` | `searchNm`, `orgId`, `startCount`, `resultCount` | `kosis-search` |
| 목록 | `statisticsList.do?method=getList` | `vwCd`(예: MT_ZTITLE 주제별), `parentListId` | — |
| 메타 | `statisticsData.do?method=getMeta` | `type`=TBL·ORG·PRD·ITM·CMMT·UNIT·SOURCE·WGT·NCD, `orgId`, `tblId` | `kosis-meta` |
| 자료 | `Param/statisticsParameterData.do?method=getList` | `orgId`, `tblId`, `itmId`, `objL1..objL8`, `prdSe`, `startPrdDe`/`endPrdDe` 또는 `newEstPrdCnt` | `kosis-data` |

KOSIS 웹 화면의 **[OpenAPI] 버튼**(통계표 조회 화면)을 누르면 현재 선택 조건 그대로의
요청 URL이 생성된다. 분류 코드 조합이 복잡하면 이 URL에서 파라미터를 옮겨 오는 게 가장 빠르다.

## 3. 식별자와 분류 파라미터

- `orgId`: 작성기관 코드 (통계청 = 101)
- `tblId`: 통계표 ID (예: `DT_1B040A3` 주민등록인구)
- `itmId`: 항목 (예: `T20` 총인구수). `ALL` 가능
- `objL1`~`objL8`: 분류 1~8단계 코드. `ALL` 또는 `+`로 여러 값 연결 (예: `11+26`)
  - **분류 단계 수는 통계표마다 다르다.** 메타(`type=ITM`)로 몇 단계인지 먼저 본다.
    필요한 단계보다 적게 넘기면 err 20/21이 난다.
- 응답 행 주요 필드: `C1`/`C1_NM`(분류값), `ITM_ID`/`ITM_NM`, `UNIT_NM`, `PRD_SE`, `PRD_DE`(시점), `DT`(값, 문자열)

`DT`는 문자열이다. 숫자 변환 시 `-`(해당없음), `…`(미상), `x`(비밀보호) 같은 기호가
섞일 수 있으니 결측으로 처리하고 개수를 보고한다.

## 4. 수록주기와 기간 형식

| prdSe | 의미 | 기간 형식 예 | 자동 분할 지원 |
|---|---|---|---|
| Y | 년 | `2023` | ✓ |
| H | 반기 | `202301`, `202302` | ✓ |
| Q | 분기 | `202301`~`202304` | ✓ |
| M | 월 | `202312` | ✓ |
| D / IR / F 등 | 일·부정기·다년 | 표마다 다름 | ✗ (수동으로 나눠 요청) |

분기·반기 형식은 통계표에 따라 다를 수 있으므로 메타(`type=PRD`) 또는 시범조회의
`PRD_DE` 값으로 확인한 뒤 `--start/--end`를 정한다.

## 5. 오류 코드와 대응

| err | 의미 | 대응 |
|---|---|---|
| 10 | 인증키 누락 | `.env`의 `KOSIS_API_KEY` 확인 |
| 11 | 인증키 기간 만료 | KOSIS에서 재발급 |
| 20 | 필수 요청변수 누락 | 분류 단계(objL) 수·itmId 확인 |
| 21 | 잘못된 요청변수 | 코드값 오타, 기간 형식 확인 |
| 30 | 조회 결과 없음 | 기간·분류 조합에 값이 없음. 빈 결과로 처리(오류 아님) |
| 31 | 조회 결과 40,000셀 초과 | 기간을 나눠 요청 — `kosis-data`가 Y/H/Q/M에서 자동 이분할 |
| 40/41 | 호출 건수·ROW 제한 | 간격을 두고 재시도, 요청 범위 축소 |
| 50 | 서버 오류 | 잠시 후 재시도 |

프록시 403(`CONNECT tunnel failed, 403`)은 KOSIS 오류가 아니라 실행 환경의
**egress 정책 차단**이다. 우회하지 말고 허용된 환경(로컬 PC)에서 실행하도록 안내한다.

## 6. 출처 표기

보고서·표·그림에는 다음 형식으로 출처를 단다 (manifest.json의 `citation` 필드가 이 형식):

> 출처: 통계청 KOSIS, 「통계표명」(통계표 ID DT_xxxx, orgId 101), YYYY.MM.DD 수집

작성기관이 통계청이 아닌 경우 기관명을 바꿔 쓴다 (메타 `type=ORG`).
