#!/bin/bash
# First-time setup of TrustKit on ovh2
# Usage: ./infra/setup-ovh2.sh
set -euo pipefail

HOST="ovh2"
APP_DIR="/opt/trustkit"

echo "=== TrustKit First-Time Setup on ovh2 ==="

# Step 1: Install system deps
echo "Step 1: Installing system dependencies..."
ssh "$HOST" << 'REMOTE'
set -euo pipefail

# Python 3.11+ and Node.js (for frontend build)
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip nodejs npm postgresql postgresql-contrib 2>/dev/null || true

# Ensure PostgreSQL is running
sudo systemctl enable --now postgresql

# Create database and user (idempotent)
sudo -u postgres psql -c "CREATE USER ndai WITH PASSWORD 'ndai';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE ndai OWNER ndai;" 2>/dev/null || true

echo "System dependencies installed"
REMOTE

# Step 2: Clone repo and install
echo "Step 2: Setting up application..."
ssh "$HOST" << REMOTE
set -euo pipefail

sudo mkdir -p "$APP_DIR"
sudo chown \$(whoami):\$(whoami) "$APP_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
    git clone https://github.com/discordwell/ndai-hackathon.git "$APP_DIR"
else
    cd "$APP_DIR" && git pull --ff-only origin main
fi

cd "$APP_DIR"

# Python venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" -q

# Frontend
cd frontend && npm install && npm run build && cd ..

echo "Application installed"
REMOTE

# Step 3: Create .env
echo ""
echo "=== Configuration ==="
read -p "OpenAI API key (or press enter to skip): " OPENAI_KEY
SECRET=$(openssl rand -hex 32)

ssh "$HOST" "cat > $APP_DIR/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://ndai:ndai@localhost:5432/ndai
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=$SECRET
LLM_PROVIDER=openai
OPENAI_API_KEY=${OPENAI_KEY:-}
OPENAI_MODEL=gpt-4o
TEE_MODE=simulated
EOF"

# Step 4: Run migrations
echo "Step 4: Running database migrations..."
ssh "$HOST" "cd $APP_DIR && source .venv/bin/activate && alembic upgrade head"

# Step 5: Install systemd service
echo "Step 5: Setting up systemd service..."
ssh "$HOST" << REMOTE
sudo cp "$APP_DIR/infra/trustkit.service" /etc/systemd/system/trustkit.service
sudo systemctl daemon-reload
sudo systemctl enable trustkit
sudo systemctl start trustkit
sleep 2
curl -sf http://localhost:8100/health > /dev/null && echo "TrustKit server healthy" || echo "Server not responding yet"
REMOTE

# Step 6: Add Caddy config
echo "Step 6: Configuring Caddy..."
ssh "$HOST" << REMOTE
# Append TrustKit config to Caddyfile if not already present
if ! grep -q "shape.discordwell.com" /etc/caddy/Caddyfile 2>/dev/null; then
    echo "" | sudo tee -a /etc/caddy/Caddyfile > /dev/null
    cat "$APP_DIR/infra/Caddyfile.shape" | sudo tee -a /etc/caddy/Caddyfile > /dev/null
    sudo caddy fmt --overwrite /etc/caddy/Caddyfile
    sudo systemctl reload caddy
    echo "Caddy config added and reloaded"
else
    echo "Caddy config already present"
fi
REMOTE

echo ""
echo "=== TrustKit Deployed ==="
echo "URL: https://shape.discordwell.com"
echo "API: https://shape.discordwell.com/api/v1/"
echo "SSH: ssh ovh2"
echo "Logs: ssh ovh2 'journalctl -u trustkit -f'"
