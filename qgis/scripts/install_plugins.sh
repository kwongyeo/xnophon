#!/usr/bin/env bash
#
# install_plugins.sh — 권장 QGIS 플러그인 일괄 설치 (Linux / macOS)
#
# 본인 컴퓨터(QGIS 데스크톱이 설치된 환경)에서 실행한다.
# qgis-plugin-manager(3liz)를 이용해 GUI 없이 plugins.txt 목록을 한 번에 설치.
#
# 사용법:
#   bash qgis/scripts/install_plugins.sh
#   QGIS_PLUGIN_DIR=/원하는/프로파일/python/plugins bash qgis/scripts/install_plugins.sh
#
# 설치 후 QGIS를 재시작하고 '플러그인 → 플러그인 관리 및 설치'에서 활성화 여부를 확인한다.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIST_FILE="${1:-$SCRIPT_DIR/plugins.txt}"

# 1) QGIS 플러그인 디렉터리 자동 탐지 (환경변수로 덮어쓸 수 있음)
detect_plugin_dir() {
  if [[ -n "${QGIS_PLUGIN_DIR:-}" ]]; then echo "$QGIS_PLUGIN_DIR"; return; fi
  local base
  case "$(uname -s)" in
    Darwin) base="$HOME/Library/Application Support/QGIS/QGIS3/profiles/default" ;;
    *)      base="$HOME/.local/share/QGIS/QGIS3/profiles/default" ;;
  esac
  echo "$base/python/plugins"
}

PLUGIN_DIR="$(detect_plugin_dir)"

echo "▶ 플러그인 설치 대상 디렉터리: $PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR"

# 2) qgis-plugin-manager 준비 (pip)
if ! command -v qgis-plugin-manager >/dev/null 2>&1; then
  echo "▶ qgis-plugin-manager 설치 중 (pip)..."
  python3 -m pip install --user --quiet qgis-plugin-manager || {
    echo "✖ qgis-plugin-manager 설치 실패. 'python3 -m pip install qgis-plugin-manager' 를 직접 실행해보세요."; exit 1; }
fi

# 3) 저장소 메타데이터 초기화/갱신
cd "$PLUGIN_DIR"
echo "▶ 공식 플러그인 저장소 메타데이터 갱신..."
qgis-plugin-manager init   >/dev/null 2>&1 || true
qgis-plugin-manager update >/dev/null 2>&1 || qgis-plugin-manager update

# 4) 목록을 읽어 순서대로 설치 (실패해도 다음으로 진행)
ok=(); fail=()
while IFS= read -r line || [[ -n "$line" ]]; do
  name="$(echo "$line" | sed 's/#.*//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [[ -z "$name" ]] && continue
  echo "──────────────────────────────────────────"
  echo "▶ 설치: $name"
  if qgis-plugin-manager install "$name"; then
    ok+=("$name")
  else
    echo "  ⚠ '$name' 설치 실패 — 이름이 plugins.qgis.org 와 정확히 일치하는지 확인하세요."
    fail+=("$name")
  fi
done < "$LIST_FILE"

# 5) 요약
echo "══════════════════════════════════════════"
echo "✔ 성공 (${#ok[@]}): ${ok[*]:-없음}"
[[ ${#fail[@]} -gt 0 ]] && echo "✖ 실패 (${#fail[@]}): ${fail[*]}"
echo
echo "다음 단계: QGIS 재시작 → '플러그인 → 플러그인 관리 및 설치 → 설치됨' 에서 활성화 확인."
echo "(실패 항목은 plugins.qgis.org 에서 정확한 플러그인 이름을 확인해 plugins.txt 를 수정 후 재실행)"
