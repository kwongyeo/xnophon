#!/bin/bash
# 주탐주예(stock-prediction) 의존성 설치 — Claude Code on the web 세션 준비.
set -euo pipefail

# 웹(원격) 세션에서만 실행
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}/stock-prediction"

# 편집모드 설치(+dev: pytest·matplotlib). 컨테이너 캐시 활용 위해 install 사용. 멱등.
python3 -m pip install -e ".[dev]" --quiet

# 모듈 실행 편의를 위해 PYTHONPATH 노출
echo "export PYTHONPATH=\"${CLAUDE_PROJECT_DIR:-.}/stock-prediction/src:\${PYTHONPATH:-}\"" >> "$CLAUDE_ENV_FILE"

echo "[session-start] 주탐주예 준비 완료 (pip install -e .[dev])"
