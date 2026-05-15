# Strategy Design — SL + RL + LLM 3중 앙상블

## 왜 3중 앙상블인가

각 모델의 약점이 서로 보완된다.

| 모델 | 강점 | 약점 |
|---|---|---|
| SL (LightGBM) | 빠른 학습, 해석 가능, 안정적 | 변화하는 시장에 적응 느림 |
| RL (PPO) | 장기 보상 최적화, 비선형 정책 | 학습 불안정, 과적합 |
| LLM (Claude) | 뉴스·공시 비정형 데이터 활용, 추론 설명 | 비용, 지연, 환각 |

## 추천 구현 순서

1. **Phase 1: SL 단독** — LightGBM으로 다음 봉 수익률 예측 → 임계값 룰. 백테스트 Sharpe 기준선 확보.
2. **Phase 2: RL 추가** — FinRL 환경에 SL 시그널을 state로 포함. PPO 학습 후 백테스트 비교.
3. **Phase 3: LLM 의사결정 레이어** — SL+RL 시그널과 뉴스를 LLM에 주고 최종 매매 결정. 저신뢰면 hold.

각 단계마다 백테스트 → 모의 → (검증 통과 시) 실거래 소액 진행.

## LLM 의사결정 프롬프트 설계

LLM은 "분석가 + 리스크 매니저" 역할. 다음 입력을 받아 JSON으로 결정한다:

```
- 종목: {symbol} ({market})
- 가격 요약: 최근 5일 OHLC, RSI, MACD
- SL 시그널: {action, confidence}
- RL 시그널: {action, confidence}
- 뉴스 헤드라인 (최근 24h): [...]
- 현재 포지션: {qty, avg_price, unrealized_pnl_pct}
- 리스크 상태: {daily_dd, total_dd, remaining_budget}

→ 출력 (JSON, structured):
{
  "action": "buy" | "hold" | "sell",
  "confidence": 0.0..1.0,
  "size_pct": 0.0..0.10,
  "rationale": "한 문장 근거"
}
```

## 앙상블 합의 룰

기본은 confidence 가중 평균이지만, **하방 보수**:

- 셋 중 하나라도 `sell`이면 매수 금지.
- LLM confidence < `veto_low_confidence`이면 hold.
- 리스크 게이트(`risk/limits.py`)가 최종 차단권.
