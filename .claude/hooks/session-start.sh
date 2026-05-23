#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Ensure Node.js (preinstalled at /opt/node22) is on PATH for this session
# so the Playwright MCP server (npx @playwright/mcp) can launch.
if [ -d /opt/node22/bin ]; then
  echo 'export PATH="/opt/node22/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
  export PATH="/opt/node22/bin:$PATH"
fi

# --- Python deps ---------------------------------------------------------
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"

# Put the venv's bin (lr-chat, lr-compare, pytest) on PATH for the session.
echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"

# --- Playwright MCP ------------------------------------------------------
# Pre-warm the npx cache so the MCP server starts without a cold download.
npx --yes @playwright/mcp@latest --help >/dev/null 2>&1 || true

# --- hwpilot CLI (required by the hwpilot skill) -------------------------
# Not published to npm — build from GitHub and install globally.
# Requires `bun` for the postbuild step (preinstalled at /root/.bun/bin).
if ! command -v hwpilot >/dev/null 2>&1; then
  if [ -d /root/.bun/bin ]; then
    export PATH="/root/.bun/bin:$PATH"
    echo 'export PATH="/root/.bun/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
  fi
  HWPILOT_SRC="$(mktemp -d)/hwpilot"
  git clone --depth 1 https://github.com/devxoul/hwpilot.git "$HWPILOT_SRC" >/dev/null 2>&1
  (cd "$HWPILOT_SRC" && npm install --silent && npm run build --silent) >/dev/null 2>&1
  npm install -g "$HWPILOT_SRC" >/dev/null 2>&1 || true
fi

# Install Chromium only if the container hasn't already provisioned it.
# (Container images may pre-stage browsers at /opt/pw-browsers — respect that.)
BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
if [ ! -d "$BROWSERS_PATH" ] || ! ls "$BROWSERS_PATH"/chromium-* >/dev/null 2>&1; then
  npx --yes playwright install chromium
fi
