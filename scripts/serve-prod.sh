#!/usr/bin/env bash
# Keep the ShiftFlow pilot backend alive: uvicorn on :8010 + the named
# Cloudflare tunnel (shiftflow-api.digitalnebula.net). Idempotent — safe to
# run from cron every 5 minutes; starts only what is missing.
set -u

API_DIR="$HOME/projects/shiftflow/apps/api"
LOG_DIR="$HOME/.local/state/shiftflow"
mkdir -p "$LOG_DIR"

# Postgres (docker) — start container if stopped
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q tbs-crm-postgres-1; then
  docker start tbs-crm-postgres-1 >/dev/null 2>&1
fi

# API
if ! curl -sf -m 3 http://localhost:8010/health >/dev/null 2>&1; then
  pkill -f "uvicorn app.main:app --port 8010" 2>/dev/null
  cd "$API_DIR" || exit 1
  setsid python3 -m uvicorn app.main:app --port 8010 \
    >> "$LOG_DIR/api.log" 2>&1 < /dev/null &
fi

# Tunnel
if ! pgrep -f "cloudflared tunnel --config $HOME/.cloudflared/shiftflow-api.yml" >/dev/null; then
  setsid cloudflared tunnel --config "$HOME/.cloudflared/shiftflow-api.yml" \
    --protocol http2 run >> "$LOG_DIR/tunnel.log" 2>&1 < /dev/null &
fi
