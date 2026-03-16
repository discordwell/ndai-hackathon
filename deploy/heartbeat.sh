#!/bin/bash
# Rate-limited heartbeat for NDAI EC2 instance.
# Sends at most once per 4 minutes. Runs SSH in background so it doesn't block.
# Called by Claude Code hooks and can be called from any automation.

LAST_FILE="/tmp/ndai-heartbeat-last-local"
KEY="$HOME/.ssh/ndai-key.pem"
INSTANCE_ID="i-0cb217910541ff0d6"
REGION="us-west-1"

# Rate limit: skip if last heartbeat was <4 min ago
NOW=$(date +%s)
if [ -f "$LAST_FILE" ]; then
  LAST=$(cat "$LAST_FILE")
  AGE=$((NOW - LAST))
  if [ "$AGE" -lt 600 ]; then
    exit 0
  fi
fi

# Check if instance is running (cached for 5 min)
STATE_CACHE="/tmp/ndai-instance-state"
STATE_AGE=999
if [ -f "$STATE_CACHE" ]; then
  STATE_AGE=$(( NOW - $(stat -f %m "$STATE_CACHE" 2>/dev/null || echo 0) ))
fi
if [ "$STATE_AGE" -gt 300 ]; then
  STATE=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "unknown")
  echo "$STATE" > "$STATE_CACHE"
else
  STATE=$(cat "$STATE_CACHE")
fi

if [ "$STATE" != "running" ]; then
  exit 0
fi

# Get IP (cached)
IP_CACHE="/tmp/ndai-instance-ip"
if [ "$STATE_AGE" -gt 300 ] || [ ! -f "$IP_CACHE" ]; then
  IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text 2>/dev/null)
  echo "$IP" > "$IP_CACHE"
else
  IP=$(cat "$IP_CACHE")
fi

[ -z "$IP" ] || [ "$IP" = "None" ] && exit 0

# Send heartbeat in background (non-blocking)
echo "$NOW" > "$LAST_FILE"
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes \
  -i "$KEY" "ec2-user@$IP" "touch /tmp/ndai-heartbeat" &>/dev/null &
