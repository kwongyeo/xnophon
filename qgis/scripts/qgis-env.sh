# qgis-env.sh — 헤드리스 QGIS 실행 환경변수
#
# 사용:  source qgis/scripts/qgis-env.sh
#
# 이 환경(컨테이너)에서 주의할 점:
#  - 기본 `python3` 은 3.11 이지만, apt QGIS 바인딩은 3.12 용으로 빌드돼 있다.
#    → PyQGIS 스크립트는 반드시 `python3.12` 로 실행한다 (아래 alias 제공).
#  - GUI/디스플레이가 없으므로 Qt 를 offscreen 플랫폼으로 띄운다.

# 화면 없이 Qt 구동
export QT_QPA_PLATFORM=offscreen
# 헤드리스 런타임 디렉터리 (XDG 경고 제거)
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-root}"
mkdir -p "$XDG_RUNTIME_DIR" 2>/dev/null && chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true
# 일부 알고리즘의 GUI 메시지 훅 비활성화
export QGIS_DISABLE_MESSAGE_HOOKS=1
# qgis_process 진행률 막대 비활성(로그 깔끔)
export QGIS_PROCESS_DISABLE_PROGRESS=1

# PyQGIS 는 3.12 인터프리터로 실행해야 한다
alias qpy='python3.12'

echo "✔ 헤드리스 QGIS 환경 적용됨 (QT_QPA_PLATFORM=offscreen)"
echo "  - CLI 분석:    qgis_process run <algorithm> --INPUT=... --OUTPUT=..."
echo "  - PyQGIS:      qpy <script.py>   (= python3.12)"
