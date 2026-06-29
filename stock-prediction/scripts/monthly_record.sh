#!/usr/bin/env bash
# 월 1회 모의투자 기록 — 모델의 현재 추천을 장부(paper_trades/ledger.csv)에 적재.
#
# 설치(매월 1일 오전 9시 실행 예):
#   crontab -e
#   0 9 1 * * /path/to/stock-prediction/scripts/monthly_record.sh >> /path/to/stock-prediction/paper_trades/cron.log 2>&1
#
# horizon은 인자로 지정(기본 40거래일≈2개월): monthly_record.sh 60
set -euo pipefail

# 스크립트 위치 기준 프로젝트 루트
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HORIZON="${1:-40}"

# venv 있으면 사용, 없으면 시스템 python (PYTHONPATH=src 로 모듈 실행)
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 모의투자 기록 시작 (horizon=${HORIZON})"
PYTHONPATH=src "$PY" -m stock_prediction.paper_trade record "$HORIZON"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 완료"
