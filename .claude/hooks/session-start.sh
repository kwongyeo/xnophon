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

# Install Chromium only if the container hasn't already provisioned it.
# (Container images may pre-stage browsers at /opt/pw-browsers — respect that.)
BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
if [ ! -d "$BROWSERS_PATH" ] || ! ls "$BROWSERS_PATH"/chromium-* >/dev/null 2>&1; then
  npx --yes playwright install chromium
fi
