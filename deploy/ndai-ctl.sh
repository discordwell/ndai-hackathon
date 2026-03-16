#!/bin/bash
# NDAI instance control — start, stop, ssh, keepalive
# Usage: ./deploy/ndai-ctl.sh [start|stop|status|ssh|logs|keepalive]
set -euo pipefail

INSTANCE_ID="i-0cb217910541ff0d6"
REGION="us-west-1"
KEY="$HOME/.ssh/ndai-key.pem"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $KEY"

get_ip() {
  aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text 2>/dev/null
}

get_state() {
  aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null
}

wait_for_ssh() {
  local ip="$1"
  echo "Waiting for SSH..."
  for i in $(seq 1 30); do
    if ssh $SSH_OPTS "ec2-user@$ip" "echo ok" &>/dev/null; then
      return 0
    fi
    sleep 3
  done
  echo "SSH timeout" && return 1
}

case "${1:-status}" in
  start)
    STATE=$(get_state)
    if [ "$STATE" = "running" ]; then
      IP=$(get_ip)
      echo "Already running at $IP"
      exit 0
    fi

    echo "Starting instance..."
    aws ec2 start-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null
    aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
    IP=$(get_ip)
    echo "Instance running at $IP"

    wait_for_ssh "$IP"

    # Install watchdog on first boot (idempotent)
    ssh $SSH_OPTS "ec2-user@$IP" << 'WATCHDOG'
# Create heartbeat watchdog script
cat > /tmp/ndai-watchdog.sh << 'WD'
#!/bin/bash
# Auto-stop if no heartbeat for 15 minutes
HEARTBEAT_FILE="/tmp/ndai-heartbeat"
MAX_AGE=900  # 15 minutes in seconds

if [ ! -f "$HEARTBEAT_FILE" ]; then
  # No heartbeat file yet — grace period on boot
  touch "$HEARTBEAT_FILE"
  exit 0
fi

AGE=$(( $(date +%s) - $(stat -c %Y "$HEARTBEAT_FILE" 2>/dev/null || stat -f %m "$HEARTBEAT_FILE") ))
if [ "$AGE" -gt "$MAX_AGE" ]; then
  logger "ndai-watchdog: no heartbeat for ${AGE}s, stopping instance"
  sudo shutdown -h now
fi
WD
chmod +x /tmp/ndai-watchdog.sh

# Install cron job (every 5 minutes)
(crontab -l 2>/dev/null | grep -v ndai-watchdog; echo "*/5 * * * * /tmp/ndai-watchdog.sh") | crontab -
touch /tmp/ndai-heartbeat
echo "Watchdog installed (auto-stop after 15min without heartbeat)"
WATCHDOG

    # Start the app
    ssh $SSH_OPTS "ec2-user@$IP" << 'APP'
cd ndai-hackathon
source .venv/bin/activate
if ! pgrep -f uvicorn > /dev/null; then
  nohup uvicorn ndai.api.app:create_app --factory --host 0.0.0.0 --port 8000 > /tmp/ndai.log 2>&1 &
  sleep 2
fi
curl -sf http://localhost:8000/health > /dev/null && echo "NDAI server running" || echo "Server failed to start — check: ssh ec2-user@$(curl -s ifconfig.me) 'tail /tmp/ndai.log'"
APP

    echo ""
    echo "=== NDAI is live ==="
    echo "URL:  http://$IP:8000"
    echo "SSH:  ssh $SSH_OPTS ec2-user@$IP"
    echo ""
    echo "Run './deploy/ndai-ctl.sh keepalive' to prevent auto-shutdown"
    ;;

  stop)
    echo "Stopping instance..."
    aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null
    echo "Instance stopping (takes ~30s). No more charges for compute."
    ;;

  status)
    STATE=$(get_state)
    echo "State: $STATE"
    if [ "$STATE" = "running" ]; then
      IP=$(get_ip)
      echo "IP:    $IP"
      echo "URL:   http://$IP:8000"
      # Check if app is responding
      if curl -sf --connect-timeout 3 "http://$IP:8000/health" > /dev/null 2>&1; then
        echo "App:   healthy"
      else
        echo "App:   not responding"
      fi
    fi
    ;;

  ssh)
    STATE=$(get_state)
    if [ "$STATE" != "running" ]; then
      echo "Instance is $STATE. Run './deploy/ndai-ctl.sh start' first."
      exit 1
    fi
    IP=$(get_ip)
    # Send heartbeat on connect
    ssh $SSH_OPTS "ec2-user@$IP" -t "touch /tmp/ndai-heartbeat; exec bash -l"
    ;;

  logs)
    IP=$(get_ip)
    ssh $SSH_OPTS "ec2-user@$IP" "tail -50 ~/ndai-hackathon/tmp/ndai.log 2>/dev/null || tail -50 /tmp/ndai.log"
    ;;

  keepalive)
    STATE=$(get_state)
    if [ "$STATE" != "running" ]; then
      echo "Instance is $STATE. Run './deploy/ndai-ctl.sh start' first."
      exit 1
    fi
    IP=$(get_ip)
    echo "Sending heartbeats to $IP every 5 minutes (Ctrl+C to stop)"
    echo "Instance will auto-stop 15 minutes after you stop this."
    while true; do
      ssh $SSH_OPTS "ec2-user@$IP" "touch /tmp/ndai-heartbeat" 2>/dev/null && \
        echo "  [$(date +%H:%M:%S)] heartbeat sent" || \
        echo "  [$(date +%H:%M:%S)] heartbeat FAILED"
      sleep 300
    done
    ;;

  deploy)
    # Quick redeploy: sync code + restart
    IP=$(get_ip)
    echo "Syncing code..."
    rsync -avz --exclude='.venv' --exclude='node_modules' --exclude='frontend/dist' \
      --exclude='__pycache__' --exclude='.git' --exclude='.env' --exclude='ndai_enclave.eif' \
      -e "ssh $SSH_OPTS" \
      "$(dirname "$(dirname "$0")")/" "ec2-user@$IP:~/ndai-hackathon/" 2>&1 | tail -3
    echo "Restarting server..."
    ssh $SSH_OPTS "ec2-user@$IP" << 'RESTART'
cd ndai-hackathon && source .venv/bin/activate
pip install -e . -q 2>/dev/null
cd frontend && npm run build 2>&1 | tail -1 && cd ..
pkill -f uvicorn || true
sleep 1
nohup uvicorn ndai.api.app:create_app --factory --host 0.0.0.0 --port 8000 > /tmp/ndai.log 2>&1 &
sleep 2
curl -sf http://localhost:8000/health > /dev/null && echo "Deployed and running" || echo "Deploy failed"
RESTART
    ;;

  *)
    echo "Usage: ndai-ctl.sh [start|stop|status|ssh|logs|keepalive|deploy]"
    echo ""
    echo "  start      Start instance, install watchdog, launch app"
    echo "  stop       Stop instance (no compute charges)"
    echo "  status     Show instance state and app health"
    echo "  ssh        SSH in (sends heartbeat on connect)"
    echo "  logs       Tail server logs"
    echo "  keepalive  Send heartbeats every 5min (Ctrl+C to stop)"
    echo "  deploy     Sync code + restart server"
    ;;
esac
