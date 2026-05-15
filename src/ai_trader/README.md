# ai_trader

AI 기반 한국·미국 주식 자동매매 서브프로젝트. 지도학습(SL) + 강화학습(RL) + LLM 의사결정의 3중 앙상블 신호를 한국투자증권 OpenAPI로 체결합니다.

> ⚠️ 이 서브프로젝트는 xnophon 모노레포의 일부입니다. 별도 GitHub 레포로 분리하려면 `git subtree split --prefix=src/ai_trader/ -b ai-trader-extract` 사용.

## 단계적 운영

```
백테스트 → 모의투자 (KIS Paper) → 실거래 (KIS Live)
```

같은 전략 코드가 모든 단계에서 그대로 동작 — `Broker` 추상화 덕분.

## 설치 (xnophon 루트에서)

```bash
pip install -e ".[ai-trader,dev]"
cp .env.example .env          # KIS·Anthropic 키 채우기
```

## 실행

```bash
trader backtest --config src/ai_trader/configs/base.yaml
trader paper    --config src/ai_trader/configs/base.yaml
trader live     --config src/ai_trader/configs/base.yaml   # KIS_ENV=live
```

## 하위 구조

| 디렉터리 | 역할 |
|---|---|
| `data/` | 시세·뉴스 수집, 캐시, 피처 |
| `models/` | SL / RL / LLM 학습 아티팩트 |
| `strategies/` | 모델 출력 → 매매 시그널 |
| `backtest/` | 이벤트 기반 시뮬레이터 |
| `execution/` | `Broker` 추상화 + KIS/Paper 구현 |
| `risk/` | 체결 직전 한도·손절·kill switch |
| `portfolio/` | 포지션·자본 배분 |
| `orchestrator/` | 메인 루프·스케줄러 |
| `utils/` | 로깅·시간·시크릿 |
| `configs/` | YAML 설정 (시장·전략·리스크) |
| `scripts/` | 일회성 학습·다운로드 |
| `tests/` | pytest |
| `docs/` | 아키텍처·KIS setup·runbook |

## 핵심 설계 원칙

1. **`Broker` 추상화** — `paper_broker` ↔ `kis_broker` 토글로 안전한 승격.
2. **`risk/`는 체결 직전 게이트** — 모델 오류도 손실 한도 내에서만.
3. **모델 vs 전략 분리** — 예측은 모델, 매매 룰은 전략.
4. **YAML 우선 설정** — 코드 변경 없이 종목·임계값·자본 튜닝.
5. **append-only 감사 로그** — 모든 주문/체결 기록 (`logs/`).
