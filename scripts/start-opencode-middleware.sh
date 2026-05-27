#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/Desktop/security_agent_middleware"
INTERCEPTOR="${ROOT}/interceptor"
LOG="/tmp/tranquera-interceptor.log"

cd "${ROOT}"

if command -v colima >/dev/null 2>&1; then
  colima status >/dev/null 2>&1 || colima start
fi

docker compose up -d postgres

cd "${INTERCEPTOR}"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 >> "${LOG}" 2>&1
