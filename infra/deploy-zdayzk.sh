#!/bin/bash
# Deploy ZDayZK to ovh2 — sync code, build, migrate, restart
# Usage: ./infra/deploy-zdayzk.sh
set -euo pipefail

HOST="ovh2"
APP_DIR="/opt/zdayzk"

echo "=== Deploying ZDayZK to ovh2 ==="

# Step 1: Sync code via git pull
echo "Pulling latest code..."
ssh "$HOST" "cd $APP_DIR && git fetch origin && git pull --ff-only origin main"

# Step 2: Install deps + build
echo "Installing and building..."
ssh "$HOST" << REMOTE
set -euo pipefail
cd "$APP_DIR"

# Python deps
source .venv/bin/activate
pip install -e ".[dev]" -q 2>/dev/null

# Frontend build
cd zdayzk-frontend && npm install --silent && npm run build 2>&1 | tail -1 && cd ..

# Database migrations (shared DB with TrustKit — safe to run from either)
if [ -f alembic.ini ]; then
    alembic upgrade head 2>&1 | tail -3
fi

echo "Build complete"
REMOTE

# Step 3: Restart service
echo "Restarting service..."
ssh "$HOST" "sudo systemctl restart zdayzk"
sleep 2

# Step 4: Health check
echo "Checking health..."
ssh "$HOST" "curl -sf http://localhost:8101/health > /dev/null && echo 'ZDayZK: healthy' || echo 'ZDayZK: FAILED'"

echo ""
echo "Deployed to https://zdayzk.com"
