#!/usr/bin/env bash
#
# setup_qgis_headless.sh — 컨테이너/서버에 QGIS + GRASS를 헤드리스로 설치한다.
#
# Ubuntu 24.04(noble) 기준. apt universe의 QGIS 3.34 LTR + GRASS 8.3을 설치하고,
# GRASS Processing 공급자를 활성화한다. GUI 없이 qgis_process(CLI)와
# PyQGIS(python3.12) 스크립팅을 쓸 수 있다. 멱등(idempotent).
#
# 사용법:  sudo bash qgis/scripts/setup_qgis_headless.sh
#
# 주의: 이 컨테이너는 임시(ephemeral)다. 세션이 끝나면 설치가 사라진다.
#       SessionStart 훅(.claude/settings.json)으로 새 세션마다 자동 실행된다.

set -uo pipefail

export DEBIAN_FRONTEND=noninteractive
export QT_QPA_PLATFORM=offscreen
export QGIS_PROCESS_DISABLE_PROGRESS=1
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-root}"
mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true

# 1) QGIS + GRASS (+ SAGA 바이너리) 설치
if command -v qgis_process >/dev/null 2>&1 && command -v grass >/dev/null 2>&1; then
  echo "✔ QGIS+GRASS 이미 설치됨: $(qgis_process --version 2>/dev/null | head -1)"
else
  echo "▶ apt 패키지 목록 갱신..."
  apt-get update -qq
  echo "▶ QGIS 3.34 LTR + GRASS 8.3 설치... (수백 MB, 수 분 소요)"
  apt-get install -y --no-install-recommends \
    qgis qgis-providers python3-qgis \
    grass grass-core \
    saga                                   # SAGA 바이너리(독립 실행용). QGIS 3.34 코어엔
                                           # SAGA 공급자가 없어 qgis_process엔 노출 안 됨.
fi

# 2) GRASS Processing 공급자 활성화 (qgis_process 프로파일 설정에 기록)
echo "▶ GRASS Processing 공급자 활성화..."
qgis_process plugins enable grassprovider >/dev/null 2>&1 || true

# 3) 검증 요약
GRASS_N=$(qgis_process list 2>/dev/null | grep -c '^	grass7:' || true)
TOTAL_N=$(qgis_process list 2>/dev/null | grep -cE '^	[a-z0-9]+:' || true)
echo "✔ 설치/구성 완료"
echo "   $(qgis_process --version 2>/dev/null | head -1)"
echo "   사용 가능한 알고리즘: ${TOTAL_N}개 (GRASS ${GRASS_N}개 포함)"
echo
echo "다음:  source qgis/scripts/qgis-env.sh   # 헤드리스 환경변수 적용"
