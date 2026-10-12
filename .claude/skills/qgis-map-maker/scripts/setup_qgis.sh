#!/usr/bin/env bash
#
# setup_qgis.sh — 헤드리스 QGIS가 준비됐는지 보장한다(멱등).
#
# 이 컨테이너는 임시(ephemeral)라 QGIS가 없을 수 있다. 없으면 apt로 설치한다.
# PyQGIS 는 python3.12 로 실행해야 한다(바인딩이 3.12용).
#
# 사용:  bash .claude/skills/qgis-map-maker/scripts/setup_qgis.sh
# 출력(stdout 마지막 줄): PyQGIS 실행에 쓸 python 경로

set -uo pipefail
export DEBIAN_FRONTEND=noninteractive QT_QPA_PLATFORM=offscreen

if ! command -v qgis_process >/dev/null 2>&1; then
  echo "▶ QGIS 3.34 LTR 설치 중... (수 분)" >&2
  # 저장소에 기존 설치 스크립트가 있으면 사용
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  if [[ -f "$ROOT/qgis/scripts/setup_qgis_headless.sh" ]]; then
    sudo bash "$ROOT/qgis/scripts/setup_qgis_headless.sh" >&2
  else
    sudo apt-get update -qq >&2
    sudo apt-get install -y --no-install-recommends qgis qgis-providers python3-qgis >&2
  fi
fi

# PyQGIS 를 import 할 수 있는 파이썬 탐색 (보통 python3.12)
for PY in python3.12 python3; do
  if "$PY" -c "from qgis.core import Qgis" >/dev/null 2>&1; then
    echo "✔ 헤드리스 QGIS 준비: $(QT_QPA_PLATFORM=offscreen qgis_process --version 2>/dev/null|head -1)" >&2
    echo "$PY"; exit 0
  fi
done
echo "✖ PyQGIS 를 불러올 파이썬을 찾지 못했습니다(python3.12 확인 필요)" >&2
exit 1
