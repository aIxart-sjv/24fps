#!/bin/bash
set -e

echo "[24FPS] Starting unified container services..."

# Start Nginx in background to serve frontend and reverse-proxy /api
nginx

# Switch to backend directory
cd /app/backend

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export APP_ENV="${APP_ENV:-development}"

# Ensure .env file exists
if [ ! -f .env ]; then
    echo "[24FPS] No .env file detected, copying from .env.example..."
    cp .env.example .env
fi

# Ensure forensic data directories exist
mkdir -p data/evidence data/artifacts data/reports data/temp data/logs data/models

# Optional auto-provisioning of default administrator account if fresh DB
ADMIN_USER="${ADMIN_USERNAME:-admin}"
ADMIN_PASS="${ADMIN_PASSWORD:-admin}"
ADMIN_NAME="${ADMIN_DISPLAY_NAME:-Administrator}"

echo "[24FPS] Applying database migrations and checking admin user..."
python scripts/create_user.py \
    --username "$ADMIN_USER" \
    --display-name "$ADMIN_NAME" \
    --password "$ADMIN_PASS" \
    --role admin 2>/dev/null || echo "[24FPS] Admin account already initialized."

echo "[24FPS] Starting FastAPI backend on http://${HOST}:${PORT}..."
exec python run.py
