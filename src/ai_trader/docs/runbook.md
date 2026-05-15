# Runbook — 운영 절차

## 일일 운영 (장 시작 전)

| 시각 (KST) | 작업 | 명령 |
|---|---|---|
| 08:30 | 전일 데이터 다운로드 | `python -m ai_trader.scripts.download_data --date today` |
| 08:45 | 학습 모델 로드, 시그널 사전계산 | (orchestrator 자동) |
| 09:00 | 국내 시장 가동 | `trader live --config ...` |
| 22:30 | 미국 시장 가동 | (orchestrator 자동) |
| 06:00+1 | 일일 리포트 생성 | `python -m ai_trader.scripts.daily_report` |

## 비상 상황 대응

### Kill switch 발동 시
1. `logs/orders.jsonl`에서 마지막 상태 확인
2. `risk/kill_switch.py`의 트리거 원인 식별 (max_dd / consecutive_losses / broker_error)
3. **즉시 청산이 필요한 경우**:
   ```bash
   python -m ai_trader.scripts.flat_all --confirm
   ```
4. 원인 분석 후 `configs/risk.yaml` 재조정 → 모의 환경 재검증

### KIS API 장애
- 시세만 끊긴 경우: 보조 데이터 소스(`pykrx`/`yfinance`)로 폴백
- 주문 실패: 자동 재시도 3회(지수 백오프) 후 알림 + 운영 중단

### 모델 이상 (NaN, 극단값)
- `risk/limits.py`의 `max_position_pct`가 1차 방어
- 시그널 sanity check (`strength` 분포 모니터)
- 학습 데이터·피처 drift 검사

## 정기 점검 (주 1회)

- [ ] 백테스트 vs 실제 손익 괴리 확인 (slippage 모델 검증)
- [ ] 모델 성능 drift (recent N일 IC, hit ratio)
- [ ] 감사 로그 백업 (`logs/orders.jsonl`)
- [ ] 의존성 보안 업데이트

## 알림 채널

- 체결: 텔레그램 (실시간)
- 에러·kill switch: 텔레그램 + 이메일
- 일일 리포트: 이메일 (08:00 KST)
