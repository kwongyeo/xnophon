#!/usr/bin/env bash
#
# setup_env.sh — 회귀분석 Python 환경을 준비한다(멱등).
#
# 이 컨테이너는 임시(ephemeral)라 세션이 끝나면 설치가 사라진다.
# 스킬 실행 전에 이 스크립트를 돌리면 프로젝트 루트에 .venv-stats 를 만들고
# requirements.txt 를 설치한다. 이미 있으면 건너뛴다.
#
# 사용:  bash .claude/skills/statistical-regression-analysis/scripts/setup_env.sh
# 출력:  venv 의 python 경로(스킬이 이 경로로 스크립트를 실행)

set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# 프로젝트 루트 탐색(.git 있는 곳), 없으면 현재 작업 디렉터리
ROOT="$(git -C "$SKILL_DIR" rev-parse --show-toplevel 2>/dev/null || pwd)"
VENV="$ROOT/.venv-stats"
PY="$VENV/bin/python"

need_install=0
if [[ ! -x "$PY" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  need_install=1
fi
# 핵심 패키지 임포트로 설치 완료 여부 확인
if ! "$PY" -c "import statsmodels, linearmodels, spreg, sklearn, openpyxl" >/dev/null 2>&1; then
  need_install=1
fi
if [[ "$need_install" == "1" ]]; then
  echo "▶ 회귀분석 패키지 설치 중... (수 분)" >&2
  "$VENV/bin/pip" install --quiet -r "$SKILL_DIR/requirements.txt" >&2
fi

echo "✔ 준비 완료: $("$PY" -c 'import statsmodels,linearmodels,spreg,sklearn;print("statsmodels",statsmodels.__version__)')" >&2
echo "$PY"   # stdout: venv python 경로
