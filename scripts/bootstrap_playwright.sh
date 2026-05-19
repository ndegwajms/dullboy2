#!/usr/bin/env bash
set -euo pipefail

# Keep browser binaries inside the project folder when running in ephemeral
# environments (e.g. Railway) so runtime lookups are stable.
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}"

# Install Chromium at startup if it has not been provisioned during build.
# This makes deployments resilient when build hooks are skipped.
if ! python - <<'PY' >/dev/null 2>&1
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    executable = Path(p.chromium.executable_path)

if not executable.exists() or not executable.is_file():
    raise SystemExit(1)
PY
then
  echo "[bootstrap] Playwright Chromium missing; installing..."
  python -m playwright install --with-deps chromium
fi

# Hand off to your normal startup command, e.g.:
#   ./scripts/bootstrap_playwright.sh uvicorn main:app --host 0.0.0.0 --port 8080
exec "$@"
