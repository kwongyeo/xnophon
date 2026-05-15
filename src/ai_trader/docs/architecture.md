# Architecture

## 데이터 흐름

```
[시세 API + 뉴스] → data/sources → data/storage (Parquet/DuckDB)
                                ↓
                          data/features
                                ↓
              ┌─────────────────┼─────────────────┐
              ↓                 ↓                 ↓
       models/supervised   models/rl        models/llm
              ↓                 ↓                 ↓
        strategies/sl     strategies/rl    strategies/llm
              └─────────────────┼─────────────────┘
                                ↓
                       strategies/ensemble
                                ↓
                       portfolio/allocator
                                ↓
                         risk (게이트)
                                ↓
                      execution/Broker
                       (paper | kis)
                                ↓
                        logs/orders.jsonl
```

## 모듈 책임

- **data**: 외부 시세·뉴스를 가져와 캐시·피처화. 모델 학습/추론의 단일 진실 원천.
- **models**: 순수 ML 아티팩트. 입력 → 예측만. 매매 룰 없음.
- **strategies**: 모델 예측을 매매 시그널로 변환. 임계값·룰이 여기에.
- **backtest**: 과거 데이터로 시그널 → 가상 체결 → 성과 평가.
- **execution**: `Broker` 추상화. paper와 kis가 동일 인터페이스 구현.
- **risk**: 체결 직전 통과 게이트. 어떤 시그널도 한도 위반 시 차단.
- **portfolio**: 현재 보유 상태와 자본 배분 룰.
- **orchestrator**: 시간대별 작업 스케줄링·전체 파이프라인 실행.

## 운영 승격 경로

| 단계 | Broker | 자본 | 검증 기준 |
|---|---|---|---|
| backtest | 없음 (in-memory) | 가상 | Sharpe > 1.0, MDD < 15% |
| paper | paper_broker → KIS 모의서버 | 가상 | 1개월 운영, 손익 일관성 |
| live | kis_broker (실전) | 소액 → 확대 | 단계적 자본 증액 |
