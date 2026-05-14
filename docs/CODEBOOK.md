# 변수 사전 (Codebook)

## 산업진흥비 (industry_promotion)
| 컬럼 | 정의 | 단위 | 출처 |
|---|---|---|---|
| `expn_090_industry_sme_energy` | 세출 분야 090 결산액 | 천원 | lofin |
| `expn_120_science_technology` | 세출 분야 120 결산액 | 천원 | lofin |
| `industry_promotion_total` | 090 + 120 | 천원 | 파생 |

회계 범위: 일반+특별 (기금 제외). 명목값.

## KOSIS 인구·복지 (kosis_population)
| 컬럼 | 정의 | 단위 | KOSIS 식별자 |
|---|---|---|---|
| `pop_total` | 주민등록 총인구(연말) | 명 | 101 / DT_1B040A3 / T20 |
| `pop_elderly_65plus` | 65세 이상 인구 | 명 | 동상, obj_l2=65PLUS (검증 필요) |
| `basic_livelihood_recipients` | 기초생활보장 수급자 | 명 | 117 / DT_117N_A0021 / T1 |

## 공통 식별자
| 컬럼 | 형식 | 비고 |
|---|---|---|
| `sido_code` | 행정표준 2자리 | 11=서울 … 50=제주 |
| `sido` | 한글 명칭 | 2024 기준 (특별자치도 반영) |
| `year` | 4자리 회계연도 | 2013–2024 |
