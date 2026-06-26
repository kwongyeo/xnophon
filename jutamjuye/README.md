# 주탐주예 (JuTamJuYe) — 멀티팩터 주가 기대수익 랭킹

향후 ~60거래일(3개월) 기대수익 상위 종목을 **미국·한국 시장별**로 랭킹하는
계량 멀티팩터 모델. `주탐(株探, 종목 탐색)` + `주예(株豫, 수익 예측)`.

## 빠른 시작

```bash
python3 jutamjuye/model.py     # numpy 필요
```

표준출력으로 시장별 전체 랭킹 + 상위 5종목의 강·약 팩터 요약을 인쇄합니다.

## 구성

| 파일 | 설명 |
|---|---|
| `model.py` | 5팩터 z-score 가중합 엔진 + 2026-06-26 데이터 스냅샷 |
| `REPORT.md` | 산출된 미국/한국 상위 5종목 랭킹과 종목별 팩터 해설 |

## 5팩터 (종합 가중치)

| 팩터 | 입력 | 가중 |
|---|---|---|
| 컨센서스(예측) | 애널 목표가 상승여력, 투자의견 | 0.30 |
| 모멘텀 | 200일선/50일선 대비 위치 | 0.25 |
| 퀄리티 | ROE, 순이익률, (-)부채비율 | 0.20 |
| 밸류 | 선행이익수익률, (-)PEG, (-)PBR | 0.15 |
| 성장 | 이익성장, 매출성장 | 0.10 |

가중치는 `model.py`의 `W` 딕셔너리에서 조정합니다. 단기일수록 컨센서스·모멘텀,
장기일수록 밸류·퀄리티 비중을 높이는 것이 일반적입니다.

## 데이터 갱신

현재 스냅샷은 코드에 인라인되어 있어 외부 의존성 없이 재현됩니다. 최신화하려면
`get_stock_info`(yfinance) 등으로 동일 필드(`twoHundredDayAverageChangePercent`,
`fiftyDayAverageChangePercent`, `forwardPE`, `priceToBook`, `trailingPegRatio`,
`returnOnEquity`, `profitMargins`, `debtToEquity`, `earningsGrowth`, `revenueGrowth`,
`targetMeanPrice`/`currentPrice`, `recommendationMean`)를 받아 `US`/`KR` 딕셔너리를 교체하세요.

> ⚠️ 연구·교육용 계량 데모입니다. 투자권유나 수익 보장이 아니며, 투자 책임은 본인에게 있습니다.
