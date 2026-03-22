#!/bin/bash
# First-time setup of ZDayZK on ovh2
# Usage: ./infra/setup-zdayzk.sh
set -euo pipefail

HOST="ovh2"
APP_DIR="/opt/zdayzk"
REPO_URL="$(git remote get-url origin)"

echo "=== Setting up ZDayZK on ovh2 ==="

# Step 1: Create app directory
echo "Creating app directory..."
ssh "$HOST" "sudo mkdir -p $APP_DIR && sudo chown ubuntu:ubuntu $APP_DIR"

# Step 2: Clone repo
echo "Cloning repository..."
ssh "$HOST" "git clone $REPO_URL $APP_DIR || (cd $APP_DIR && git pull --ff-only origin main)"

# Step 3: Python venv + deps
echo "Setting up Python environment..."
ssh "$HOST" << REMOTE
set -euo pipefail
cd "$APP_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q
echo "Python deps installed"
REMOTE

# Step 4: Frontend build
echo "Building frontend..."
ssh "$HOST" << REMOTE
set -euo pipefail
cd "$APP_DIR/frontend-zk"
npm install --silent
npm run build 2>&1 | tail -1
echo "Frontend built"
REMOTE

# Step 5: Create .env (prompt for API key)
echo ""
read -rp "Enter OPENAI_API_KEY for zdayzk instance: " OPENAI_KEY
SECRET_KEY=$(openssl rand -hex 32)

# Use same SECRET_KEY as TrustKit for SSO (shared DB)
TRUSTKIT_SECRET=$(ssh "$HOST" "grep '^SECRET_KEY=' /opt/trustkit/.env 2>/dev/null | cut -d= -f2" || echo "$SECRET_KEY")
if [ -z "$TRUSTKIT_SECRET" ]; then
    TRUSTKIT_SECRET="$SECRET_KEY"
fi

ssh "$HOST" "cat > $APP_DIR/.env << 'ENVEOF'
DATABASE_URL=postgresql+asyncpg://ndai:ndai@localhost:5432/ndai
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=$TRUSTKIT_SECRET
LLM_PROVIDER=openai
OPENAI_API_KEY=$OPENAI_KEY
OPENAI_MODEL=gpt-4o
TEE_MODE=simulated
FRONTEND_DIR=$APP_DIR/frontend-zk/dist
ENVEOF"
echo ".env created (SECRET_KEY shared with TrustKit for SSO)"

# Step 6: Run migrations
echo "Running database migrations..."
ssh "$HOST" "cd $APP_DIR && source .venv/bin/activate && alembic upgrade head 2>&1 | tail -5"

# Step 7: Install systemd service
echo "Installing systemd service..."
ssh "$HOST" "sudo cp $APP_DIR/infra/zdayzk.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable zdayzk && sudo systemctl start zdayzk"
sleep 2
ssh "$HOST" "sudo systemctl is-active zdayzk && echo 'Service running' || echo 'Service FAILED'"

# Step 8: Install Caddy config
echo "Installing Caddy config..."
ssh "$HOST" "sudo cp $APP_DIR/infra/Caddyfile.zdayzk /etc/caddy/sites/zdayzk.com && sudo systemctl reload caddy"

# Step 9: Health check
echo "Running health check..."
sleep 3
ssh "$HOST" "curl -sf http://localhost:8101/health > /dev/null && echo 'ZDayZK: healthy' || echo 'ZDayZK: FAILED'"

echo ""
echo "=== Setup complete ==="
echo "Set DNS A records for zdayzk.com and www.zdayzk.com to 15.204.59.61"
echo "Caddy will auto-provision HTTPS via Let's Encrypt once DNS propagates"
