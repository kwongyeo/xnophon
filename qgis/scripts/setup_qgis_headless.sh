#!/usr/bin/env bash
#
# setup_qgis_headless.sh — 컨테이너/서버에 QGIS를 헤드리스로 설치한다.
#
# Ubuntu 24.04(noble) 기준. apt universe의 QGIS 3.34 LTR을 설치하며,
# GUI 없이 qgis_process(CLI)와 PyQGSI(python3.12) 스크립팅을 쓸 수 있게 한다.
# 멱등(idempotent) — 이미 설치돼 있으면 건너뛴다.
#
# 사용법:  sudo bash qgis/scripts/setup_qgis_headless.sh
#
# 주의: 이 컨테이너는 임시(ephemeral)다. 세션이 끝나면 설치가 사라지므로,
#       새 세션마다 이 스크립트를 다시 실행해야 한다(SessionStart 훅 권장).

set -euo pipefail

if command -v qgis_process >/dev/null 2>&1; then
  echo "✔ QGIS 이미 설치됨: $(qgis_process --version 2>/dev/null | head -1)"
  exit 0
fi

echo "▶ apt 패키지 목록 갱신..."
apt-get update -qq

echo "▶ QGIS(3.34 LTR) 헤드리스 설치... (수백 MB, 수 분 소요)"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  qgis qgis-providers python3-qgis

echo "✔ 설치 완료: $(QT_QPA_PLATFORM=offscreen qgis_process --version 2>/dev/null | head -1)"
echo
echo "다음:  source qgis/scripts/qgis-env.sh   # 헤드리스 환경변수 적용"
echo "테스트: qgis_process plugins"
