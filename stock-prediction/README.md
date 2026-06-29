# 주탐주예 (主探主豫) — 주식탐색과 주가예측

**주탐주예**(株探株豫): 한국(KRX: KOSPI/KOSDAQ)·미국 시장 종목을 **탐색(주식탐색)**하고
가격·재무·거시·심리 데이터로 단기~중기 수익률을 **예측(주가예측)**하는 연구·실험 파이프라인.

> CLI 명령은 `sp-*` 접두어(stock-prediction)를 그대로 사용한다(아래 표 참조).

> ⚠️ 면책: 본 프로젝트는 연구·학습 목적입니다. 어떤 출력도 투자 자문이 아니며,
> 실거래 사용에 따른 손실 책임은 사용자에게 있습니다.

## 설계 원칙

1. **누수(leakage) 방지** — 모든 피처는 시점 t 이전 정보만 사용. 타깃은 t+1…t+h 미래 수익률.
2. **재현성** — 원본 데이터(`data/raw`)는 불변, 변환은 코드로만. 설정은 `config/`에 고정.
3. **워크포워드 검증** — 무작위 분할 대신 시간순(rolling/expanding) 백테스트.
4. **모듈 분리** — 수집 → 피처 → 모델 → 백테스트 → 평가 단계가 독립적으로 교체 가능.

## 디렉터리 구조

```
stock-prediction/
├── README.md
├── pyproject.toml                패키지 메타 + 의존성 + 진입점
├── .env.example                  API 키 템플릿
├── .gitignore
│
├── config/
│   └── config.yaml               유니버스/기간/타깃/모델 하이퍼파라미터
│
├── data/                         (gitignore — 원본/중간 산출물)
│   ├── raw/                      수집 원본 (불변, append-only)
│   ├── interim/                  정합·결측 처리 중간물
│   ├── processed/                학습용 피처 매트릭스 (parquet)
│   └── external/                 정적 참조표 (티커 목록, 휴장일, 섹터 매핑)
│
├── src/stock_prediction/
│   ├── __init__.py
│   ├── config.py                 config.yaml 로더
│   ├── data/
│   │   ├── schema.py             표준 OHLCV / 재무 / 심리 스키마
│   │   ├── loaders.py            raw → interim → processed 변환
│   │   └── collectors/           데이터 소스 어댑터
│   │       ├── krx.py            한국 시세 (pykrx / FinanceDataReader)
│   │       ├── dart.py           한국 재무·공시 (OpenDART)
│   │       ├── yfinance_us.py    미국 시세·재무 (yfinance)
│   │       ├── macro.py          거시지표 (FRED / ECOS)
│   │       └── news.py           뉴스·검색 트렌드 (Naver) → 감성 점수
│   ├── features/
│   │   ├── technical.py          이동평균·RSI·MACD·볼린저·변동성 등
│   │   ├── fundamental.py        PER/PBR/ROE/부채비율 등
│   │   └── sentiment.py          뉴스 감성·검색량 피처
│   ├── models/
│   │   ├── baseline.py           naive / 로지스틱 / 선형
│   │   ├── tree.py               LightGBM / XGBoost
│   │   └── deep.py               LSTM / GRU / Transformer (선택)
│   ├── backtest/
│   │   ├── splitter.py           워크포워드 시간분할
│   │   └── engine.py             신호 → 포지션 → 수익률 시뮬
│   ├── evaluation/
│   │   └── metrics.py            예측 지표 + 투자 지표
│   └── pipeline.py               end-to-end 실행 (collect→train→backtest)
│
├── notebooks/                    탐색·시각화 (EDA)
├── docs/
│   └── data-sources.md           도입할 데이터 소스 상세 (★ 핵심 문서)
├── scripts/                      일회성 수집·점검 스크립트
└── tests/                        pytest 단위 테스트
```

## 빠른 시작

```bash
cd stock-prediction
python3 -m venv .venv
.venv/bin/pip install -e .

cp .env.example .env       # API 키 채우기 (DART, FRED, Naver는 무료)
# 설정 수정: config/config.yaml (유니버스/기간/타깃)

.venv/bin/sp-poc           # 0단계 PoC (삼성·AAPL 시세+재무 수집→정규화→피처/타깃)
.venv/bin/sp-baseline      # 1단계 베이스라인 (워크포워드 횡단면 예측+백테스트)
.venv/bin/sp-stage2        # 2단계 (가격 vs 가격+펀더멘털 공정 비교)
.venv/bin/sp-pipeline      # 전체 파이프라인 (수집→피처→학습→백테스트)
```

### 실전 활용 도구 (연구·교육용, 투자자문 아님)

```bash
sp-picks            # 최신 단면 모델 랭킹(기본 2개월). sp-picks 60 = 3개월
sp-paper record 40  # 모의투자: 현재 추천을 장부에 기록(2개월 horizon)
sp-paper record 40 2026-01-15   # 과거 시점으로 기록(누수 없이) — 백테스트형 검증
sp-paper report     # 장부의 모든 포지션을 최신가로 평가(원화 기준)
sp-paper report 15  # 15% 손절 규칙 시뮬레이션 적용
```

`report`는 **원화(KRW) 기준**으로 평가한다(미국 포지션은 실제 USD/KRW 환율 반영):
- **원화순익**: US는 환율 레벨변동 + 환전 스프레드(왕복 ~50bp) 포함. `현지` 컬럼은 현지통화 참고치.
- **손절 시뮬**(`report N`): 보유 중 종가가 진입가×(1−N%) 이하로 내려가면 그날 청산.
- **누적 자산곡선**: 활성 포지션 동일가중 일별 NAV → 터미널 스파크라인 +
  `paper_trades/equity_curve.csv` + `equity_curve.png`(matplotlib 있을 때). 벤치마크(KRW) 동시 표시.

`sp-paper`는 추천을 `paper_trades/ledger.csv`에 진입가와 함께 쌓고, `report`가 매번
최신 가격으로 수익·승률·청산여부를 재계산한다. `report`는 다음을 반영:
- **시장별 현실 비용**: KR 왕복 ~30bp(매도 거래세 18bp+수수료+슬리피지), US 왕복 ~110bp
  (원↔달러 환전 스프레드 ~100bp+수수료). 값은 `paper_trade.COST_BPS`에서 조정.
- **벤치마크 대비 초과수익**: 각 포지션을 같은 보유기간의 KOSPI(KR)·S&P500(US)과 비교.
  "초과 = 순수익 − 벤치마크", "벤치초과율 = 지수를 이긴 비율".

#### 월별 자동 기록 (cron)

```bash
crontab -e
# 매월 1일 09:00 에 그 시점 추천을 장부에 기록(2개월 horizon)
0 9 1 * * /path/to/stock-prediction/scripts/monthly_record.sh 40 >> /path/to/stock-prediction/paper_trades/cron.log 2>&1
```

이렇게 매월 자동 적재하고, 가끔 `sp-paper report`로 누적 성과·벤치마크 대비를 확인한다.

## 구현 진행 (단계별 로드맵)

| 단계 | 상태 | 산출물 |
|---|---|---|
| 0. PoC | ✅ 완료 | `sp-poc` — 삼성·AAPL 실데이터 수집·정규화·피처·타깃 |
| 1. 베이스라인 | ✅ 완료 | `sp-baseline` — 가격피처만 / [결과](docs/stage1-baseline-results.md): IC≈0, 벤치마크 미달 |
| 2. 펀더멘털 | ✅ 완료 | `sp-stage2` — PIT 재무 추가 / [결과](docs/stage2-fundamental-results.md): 개선 비결정적 |
| ★ 표본확대 | ✅ 완료 | 한국+미국 50종목 재실행 / [결과](docs/stage-expanded-kr-us-results.md): 큰 표본에서도 단기 신호 미확인(견고) |
| ★ 기간스윕 | ✅ 완료 | `sp-horizon` 5/20/60일 / [결과](docs/horizon-sweep-results.md): **펀더멘털 RankIC 기여가 기간과 함께↑, 60일서 0.13 — 첫 실질 신호** |
| ★ 롱숏중립 | ✅ 완료 | `sp-longshort` / [결과](docs/longshort-results.md): **신호가 베타 아닌 진짜 알파 확인(롱숏 샤프 1.1~1.6), 단 표본 작음** |
| 2b. 분기펀더 | ✅ 완료 | `sp-stage3` / [결과](docs/stage3-quarterly-macro-results.md): **분기 갱신이 LightGBM RankIC -0.01→0.03, 롱숏 샤프 -0.04→0.92로 개선** |
| 3. 레짐 | ✅ 완료 | `sp-stage3` 레짐 분할 / **저VIX 샤프 2.77 vs 고VIX -0.55 — 강한 국면 의존성** |
| ★ 레짐필터 | ✅ 완료 | `sp-regime` / [결과](docs/regime-strategy-results.md): **트레일링 VIX 필터로 샤프 0.92→1.47, MDD 반토막 (표본 작음)** |
| ★ 시장중립 | ✅ 완료 | `sp-neutral` / [결과](docs/market-neutral-results.md): **시장 내 정규화로 샤프↑, MDD -33%→-11% — 신호가 시장 내부서도 유효** |
| ★ 최종결합 | ✅ 완료 | `sp-final` / [결과](docs/capstone-results.md): 분기+시장중립+레짐필터 누적 ablation |
| ★ 장기검증 | ✅ 완료 | 5년 재실행 / [결과](docs/longer-history-validation.md): **C1·C2 견고, C3(레짐필터)는 과최적화로 교정 — 약세장 포함 샤프 ~1.0** |
| ★ 섹터중립 | ✅ 완료 | `sp-sector` / [결과](docs/sector-neutral-results.md): 비결정적 — 45종목·9섹터(일부 1~3종목)로 검증 불가, 넓은 유니버스 필요 |
| 4. 심리 | ✅ 완료 | `sp-stage4` / [결과](docs/stage4-attention-results.md): **검색 관심도는 기여 없음(음의 결과) — 검색량은 방향성 없는 프록시, 진짜 감성모델 필요** |

### 핵심 결과 (누적 ablation, h=20 롱숏 LightGBM, **5년·2022 약세장 포함**)

| 구성 | 샤프 | MDD |
|---|---:|---:|
| C0 원조(풀링+연간) | -0.26 | -39.7% |
| C1 +분기 펀더멘털 | 0.64 | -27.4% |
| C2 +시장중립 | **1.07** | -19.9% |
| C3 +레짐필터 | 0.94 | **-11.8%** |

> **장기 검증 결론**([상세](docs/longer-history-validation.md)): 분기 펀더멘털·시장중립은
> 약세장 포함 5년에서도 견고(샤프 ~1.0). **단 레짐필터는 샤프를 못 올리고 드로다운만
> 축소** — 2년 샘플의 큰 상승(1.57)은 과최적화였음이 장기 검증으로 교정됨.
> 연구·학습용이며 실거래 전략·투자자문이 아니다.

> 단계1 핵심 결과: **가격/기술적 피처만으로는 횡단면 예측 신호가 사실상 없으며
> (IC≈0), 상위 K종목 전략이 동일가중 벤치마크를 위험조정 기준으로 이기지 못한다.**
> 이는 정상적인 기준선이며, 이후 단계가 넘어야 할 기준이다. 상세: [docs/stage1-baseline-results.md](docs/stage1-baseline-results.md)

## 도입할 데이터

요약 표는 아래, **상세·발급 절차·통합 코드 예시는 [docs/data-sources.md](docs/data-sources.md)** 참조.

| 범주 | 소스 | 한국/미국 | 비용 | 용도 |
|---|---|---|---|---|
| 가격(OHLCV) | pykrx, FinanceDataReader | KR | 무료 | 핵심 입력·타깃 산출 |
| 가격(OHLCV) | yfinance | US | 무료 | 핵심 입력·타깃 산출 |
| 재무·공시 | OpenDART | KR | 무료(키) | 펀더멘털 피처 |
| 재무 | yfinance financials | US | 무료 | 펀더멘털 피처 |
| 거시지표 | FRED, 한국은행 ECOS | US/KR | 무료(키) | 금리·환율·물가 레짐 |
| 뉴스·심리 | Naver 검색/뉴스 | KR | 무료(키) | 감성·검색량 피처 |
| 참조표 | KRX 상장목록·휴장일·섹터 | KR | 무료 | 유니버스·정합 |

이 저장소가 실행되는 환경에는 **OpenDART · 미국주식 · Naver 검색 MCP 도구가 이미 연결**되어
있어, API 키 없이도 프로토타이핑 단계의 데이터 확보가 가능하다(상세: data-sources.md).

## 라이선스

MIT
