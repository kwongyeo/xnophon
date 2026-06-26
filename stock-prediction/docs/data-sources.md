# 도입할 데이터 소스 (Data Sources)

주식 수익률 예측 모델에 입력할 데이터를 5개 범주로 구성한다.
각 소스는 **수집 → `data/raw` 저장 → 표준 스키마 정규화 → 피처화** 흐름을 따른다.

설계 원칙: **모든 피처는 시점 t 이전 데이터만 사용**(look-ahead 방지),
**원본은 불변(append-only)**, **재무·공시는 보고서 "공개일" 기준 시점 정렬**(point-in-time).

---

## 1. 가격 데이터 (Price / OHLCV) — 핵심 입력·타깃

모델의 1차 입력이자 예측 **타깃(미래 수익률)**의 산출 근거.

| 시장 | 1순위 라이브러리 | 대안 | 비고 |
|---|---|---|---|
| 한국 (KOSPI/KOSDAQ) | `pykrx` | `FinanceDataReader` | 일봉 OHLCV, 거래대금, 시총, 외국인/기관 수급 |
| 미국 | `yfinance` | Stooq, Alpha Vantage | 일봉/분봉, 수정주가(adjusted close) |

수집 필드(표준 스키마, `data/schema.py`):
`date, ticker, open, high, low, close, adj_close, volume, value(거래대금), market_cap`

주의:
- **수정주가** 사용(배당·액면분할 반영). 미수정 종가로 수익률 계산 시 왜곡.
- 한국은 **상·하한가**, 거래정지일 처리 필요.
- 타깃 정의 예: `ret_{t+1} = adj_close[t+1]/adj_close[t] - 1`, 또는 h일 누적수익률, 또는 방향(상승/하락) 분류.

```python
# 한국 — pykrx
from pykrx import stock
df = stock.get_market_ohlcv("20200101", "20241231", "005930")  # 삼성전자

# 미국 — yfinance
import yfinance as yf
df = yf.download("AAPL", start="2020-01-01", auto_adjust=True)
```

> 이 환경의 MCP: `mcp__PlayMCP__UsStockInfo-get_historical_stock_prices` 로 미국 종목 시세를
> 키 없이 즉시 조회 가능(프로토타이핑용).

---

## 2. 재무·공시 데이터 (Fundamentals) — 펀더멘털 피처

밸류에이션·수익성·건전성 피처의 원천. 분기 단위, **공시 시점 정렬**이 생명.

| 시장 | 소스 | 발급 |
|---|---|---|
| 한국 | **OpenDART** (금융감독원) | https://opendart.fss.or.kr → 무료 API 키 |
| 미국 | `yfinance` financials / SEC EDGAR | 무료 |

수집 항목 → 파생 피처:
- 손익: 매출액, 영업이익, 순이익 → 성장률, 영업이익률
- 재무상태: 자산, 부채, 자본 → 부채비율, 유동비율
- 밸류에이션: PER, PBR, PSR, 배당수익률 (시총과 결합 산출)
- 수익성: ROE, ROA
- 주주: 최대주주 지분, 자사주, 임원 보유 변동 (수급·신뢰 신호)

> 이 환경의 MCP (키 없이 사용 가능):
> - `mcp__PlayMCP__opendart-get_full_financial_statement` — 전체 재무제표
> - `mcp__PlayMCP__opendart-get_financial_index` — 재무비율
> - `mcp__PlayMCP__opendart-get_dividend_info` / `get_major_stock` / `get_executive_stock`
> - `mcp__PlayMCP__opendart-search_disclosures` — 공시 이벤트(증자/합병 등)
> - `mcp__PlayMCP__UsStockInfo-get_financial_statement` / `get_holder_info` — 미국

⚠️ **Point-in-time 주의**: 2024Q1 실적은 보통 5월 중순에 공개된다. 학습 시 "발표일"
이전에 그 수치를 쓰면 미래정보 누수. 각 재무행에 `disclosed_at`(공개일)을 함께 저장하고
피처 조인은 `disclosed_at <= t` 조건으로만 한다.

---

## 3. 거시·시장 지표 (Macro) — 레짐 피처

개별 종목을 넘어 시장 전체 환경(금리·환율·물가·유동성)을 설명.

| 지표 | 소스 | 발급 |
|---|---|---|
| 미국 금리·물가·고용 (DGS10, CPI, FEDFUNDS 등) | **FRED** | https://fred.stlouisfed.org → 무료 키 |
| 한국 기준금리·환율·통화량 | **한국은행 ECOS** | https://ecos.bok.or.kr → 무료 키 |
| 시장 벤치마크 (KOSPI지수, S&P500, VIX) | pykrx / yfinance | 무료 |
| 환율 (USD/KRW), 유가, 금 | FinanceDataReader / yfinance | 무료 |

파생 피처: 금리 스프레드(장단기), VIX 수준·변화, 지수 대비 종목 상대강도(베타),
시장 모멘텀 레짐(상승장/하락장 더미).

---

## 4. 뉴스·심리 데이터 (Sentiment / Alternative) — 심리 피처

가격에 선행하거나 변동성을 키우는 비정형 신호.

| 신호 | 소스 | 발급 |
|---|---|---|
| 뉴스 기사 (제목/요약) | **Naver 뉴스 검색** | https://developers.naver.com → 무료 키 |
| 검색 트렌드 (관심도) | **Naver DataLab** | 무료 키 |
| 미국 종목 추천·뉴스 | yfinance recommendations | 무료 |

처리: 종목명/티커로 일자별 기사 수집 → (a) **기사량 급증**(관심도 스파이크) →
(b) 한국어 금융 감성모델(KR-FinBERT 등)으로 **감성 점수**(−1~+1) → 일별 집계.

> 이 환경의 MCP (키 없이 사용 가능):
> - `mcp__PlayMCP__NaverSearch-search_news` — 뉴스 검색
> - `mcp__PlayMCP__NaverSearch-datalab_search` — 검색량 추이
> - `mcp__PlayMCP__UsStockInfo-get_recommendations` — 미국 애널리스트 추천 변화

⚠️ 감성 피처도 누수 주의: 기사 "발행 시각" 이전 시점에 사용 금지. 장중 기사는 다음 거래일 반영.

---

## 5. 참조·정적 데이터 (Reference) — 정합성

`data/external/`에 정적 저장, 주기적 갱신.

- **상장 종목 목록**(티커·종목명·시장구분·섹터/업종) — 유니버스 정의
- **거래소 휴장일 캘린더** — 영업일 정렬, 결측 vs 휴장 구분
- **섹터/산업 분류 매핑** — 섹터 상대 피처, 그룹 정규화
- **상장폐지·종목코드 변경 이력** — **생존편향(survivorship bias) 제거**에 필수

⚠️ 현재 상장 종목만으로 과거를 학습하면 "살아남은 종목"만 보게 되어 성과가 과대평가된다.
백테스트 기간 시점에 실제 상장돼 있던 종목으로 유니버스를 구성해야 한다.

---

## 권장 수집 로드맵 (단계별)

| 단계 | 범위 | 목표 |
|---|---|---|
| **0. PoC** | MCP 도구로 소수 종목(예: 삼성전자, AAPL) 시세+재무 | 파이프라인 골격 검증 |
| **1. 베이스라인** | 가격(1) + 기술적 피처만, KOSPI200 유니버스 | 가격만으로 기준선 성능 |
| **2. 펀더멘털** | + DART/yfinance 재무(2), point-in-time 정렬 | 밸류·수익성 피처 추가 |
| **3. 레짐** | + 거시지표(3) | 시장 환경 조건부 성능 |
| **4. 심리** | + 뉴스/검색(4), 감성모델 | 대체데이터 효과 검증 |

각 단계마다 **워크포워드 백테스트**로 직전 단계 대비 개선 여부를 평가한다.

## 데이터 품질 체크리스트

- [ ] 수정주가 사용 (배당·분할 반영)
- [ ] 재무·공시 point-in-time(`disclosed_at`) 정렬
- [ ] 생존편향 제거(상폐 종목 포함 유니버스)
- [ ] 결측 vs 휴장 구분, 전진충전(ffill) 한도 설정
- [ ] 이상치(거래정지·상한가) 플래그
- [ ] 모든 시계열 timezone·영업일 캘린더 통일
- [ ] train/test 시간 경계에서 피처 누수 단위테스트
