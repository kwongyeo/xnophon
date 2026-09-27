#!/usr/bin/env bash
# ComfyUI + YuE2 음악 모델 자동 설치 (Linux / macOS)
#   bash install_linux_mac.sh [설치경로]       기본: ~/ComfyUI
# 이미 ComfyUI git 설치본이 있으면 그 경로를 주면 업데이트만 함.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
COMFY_DIR="${1:-$HOME/ComfyUI}"
MODEL="yue2_3b_int8_convrot.safetensors"
MODEL_URL="https://huggingface.co/Comfy-Org/YuE2/resolve/main/checkpoints/$MODEL"

step() { printf '\n==> %s\n' "$*"; }

if [ -f "$COMFY_DIR/main.py" ]; then
  step "기존 ComfyUI 업데이트: $COMFY_DIR"
  git -C "$COMFY_DIR" pull --ff-only
else
  step "ComfyUI 설치: $COMFY_DIR"
  git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
fi

if [ ! -x "$COMFY_DIR/venv/bin/python" ]; then
  step "파이썬 가상환경 생성"
  python3 -m venv "$COMFY_DIR/venv"
fi
PY="$COMFY_DIR/venv/bin/python"
step "의존성 설치 (PyTorch 포함, 수 GB)"
"$PY" -m pip install -U pip
# requirements.txt 에는 torch 류가 없으므로 먼저 설치 (AMD ROCm 은 ComfyUI README 의 index-url 사용)
"$PY" -m pip install torch torchvision torchaudio
"$PY" -m pip install -r "$COMFY_DIR/requirements.txt"

VER=$(sed -n 's/__version__ = "\(.*\)"/\1/p' "$COMFY_DIR/comfyui_version.py")
echo "ComfyUI 버전: $VER"
[ -f "$COMFY_DIR/comfy_extras/nodes_yue2.py" ] || { echo "YuE2 노드 없음 (v0.36.0 이상 필요)"; exit 1; }

step "YuE2 모델 다운로드 (3.96GB, 이어받기 지원)"
mkdir -p "$COMFY_DIR/models/checkpoints"
curl -L --fail --retry 5 -C - -o "$COMFY_DIR/models/checkpoints/$MODEL" "$MODEL_URL"

step "config.json 작성"
cat > "$HERE/config.json" <<EOF
{
  "comfy_dir": "$COMFY_DIR",
  "python": "$PY",
  "server": "127.0.0.1:8188",
  "ckpt": "$MODEL",
  "extra_args": []
}
EOF

echo
echo "설치 완료!"
echo "  ComfyUI 실행   : $PY $COMFY_DIR/main.py   (http://127.0.0.1:8188)"
echo "  노래 자동 생성 : python3 $HERE/generate_music.py --song $HERE/songs/example_ko_ballad.json"
