#!/bin/bash
# Set up NDAI on a freshly launched Nitro EC2 instance
# Usage: ./deploy/setup.sh <public-ip> [key-name]
set -euo pipefail

HOST="${1:?Usage: ./deploy/setup.sh <public-ip> [key-name]}"
KEY_NAME="${2:-ndai-key}"
SSH_KEY="$HOME/.ssh/${KEY_NAME}.pem"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"

if [ ! -f "$SSH_KEY" ]; then
  echo "Error: SSH key not found at $SSH_KEY"
  echo "Provide key name as second argument, or place key at expected path"
  exit 1
fi

SSH="ssh $SSH_OPTS -i $SSH_KEY ec2-user@$HOST"
SCP="scp $SSH_OPTS -i $SSH_KEY"

echo "=== NDAI Setup on $HOST ==="

# Wait for SSH to be available
echo "Waiting for SSH..."
for i in $(seq 1 30); do
  if $SSH "echo ok" &>/dev/null; then break; fi
  sleep 5
done

# Step 1: Install system dependencies
echo "Step 1: Installing system dependencies..."
$SSH << 'REMOTE'
set -euo pipefail

# Install packages
sudo dnf install -y docker git python3.11 python3.11-pip nodejs npm nginx \
  aws-nitro-enclaves-cli aws-nitro-enclaves-cli-devel 2>/dev/null || \
sudo yum install -y docker git python3.11 python3.11-pip nodejs npm nginx \
  aws-nitro-enclaves-cli aws-nitro-enclaves-cli-devel 2>/dev/null

# Enable services
sudo systemctl enable --now docker
sudo systemctl enable --now nitro-enclaves-allocator

# Configure allocator
sudo tee /etc/nitro_enclaves/allocator.yaml > /dev/null << 'ALLOC'
---
memory_mib: 1600
cpu_count: 2
ALLOC
sudo systemctl restart nitro-enclaves-allocator

# Add user to required groups
sudo usermod -aG ne,docker ec2-user

echo "System dependencies installed"
REMOTE

echo "Step 1 done"

# Step 2: Clone repo and set up Python
echo "Step 2: Cloning repo and setting up..."
$SSH << 'REMOTE'
set -euo pipefail

# Need new group permissions
newgrp docker << 'INNER'
  # Clone repo
  if [ ! -d ndai-hackathon ]; then
    git clone https://github.com/discordwell/ndai-hackathon.git
  else
    cd ndai-hackathon && git pull && cd ..
  fi

  cd ndai-hackathon

  # Start PostgreSQL + Redis via docker compose
  docker compose up -d
  echo "Waiting for PostgreSQL..."
  for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U ndai &>/dev/null; then
      echo "PostgreSQL ready"
      break
    fi
    sleep 2
  done

  # Python venv
  python3.11 -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev]"

  # Frontend
  npm --prefix frontend install
  npm --prefix frontend run build

  echo "Application installed"
INNER
REMOTE

echo "Step 2 done"

# Step 3: Build enclave image
echo "Step 3: Building enclave EIF (this takes a minute)..."
$SSH << 'REMOTE'
set -euo pipefail
newgrp docker << 'INNER'
  cd ndai-hackathon
  chmod +x enclave-build/build.sh
  ./enclave-build/build.sh 2>&1 | tee /tmp/enclave-build.log
  echo ""
  echo "=== PCR VALUES (save these) ==="
  grep -A3 "PCR" /tmp/enclave-build.log || echo "Check /tmp/enclave-build.log for PCR values"
INNER
REMOTE

echo "Step 3 done"

# Step 4: Create .env (prompt for API key)
echo ""
echo "=== Configuration ==="
read -p "Anthropic API key: " ANTHROPIC_KEY
SECRET=$(openssl rand -hex 32)

$SSH "cat > ~/ndai-hackathon/.env << EOF
DATABASE_URL=postgresql+asyncpg://ndai:ndai@localhost:5432/ndai
REDIS_URL=redis://localhost:6379/0
TEE_MODE=nitro
ENCLAVE_EIF_PATH=ndai_enclave.eif
ENCLAVE_CPU_COUNT=2
ENCLAVE_MEMORY_MIB=1600
ENCLAVE_VSOCK_PORT=5000
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
SECRET_KEY=$SECRET
SHAMIR_K=3
SHAMIR_N=5
BREACH_DETECTION_PROB=0.005
BREACH_PENALTY=7500000000
MAX_NEGOTIATION_ROUNDS=5
NEGOTIATION_TIMEOUT_SEC=300
EOF"

echo "Step 4 done"

# Step 5: Run database migrations
echo "Step 5: Running database migrations..."
$SSH << 'REMOTE'
cd ndai-hackathon
source .venv/bin/activate
if [ -f alembic.ini ]; then
  alembic upgrade head
  echo "Migrations applied"
else
  echo "No alembic.ini yet — skipping migrations"
fi
REMOTE

echo "Step 5 done"

# Step 6: Install systemd service + nginx
echo "Step 6: Setting up systemd service and nginx..."
$SSH << 'REMOTE'
set -euo pipefail
cd ndai-hackathon

# Install systemd service
sudo cp deploy/ndai.service /etc/systemd/system/ndai.service
sudo systemctl daemon-reload
sudo systemctl enable ndai
sudo systemctl restart ndai

# Install nginx config
sudo cp deploy/nginx.conf /etc/nginx/conf.d/ndai.conf
# Remove default server block if present
sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx

sleep 2
curl -sf http://localhost:8000/health && echo " — NDAI server healthy" || echo "Server not yet responding"
REMOTE

echo "Step 6 done"

echo ""
echo "=== NDAI Deployed ==="
echo "URL: http://$HOST (nginx) or http://$HOST:8000 (direct)"
echo "SSH: ssh -i $SSH_KEY ec2-user@$HOST"
echo "Logs: journalctl -u ndai -f"
