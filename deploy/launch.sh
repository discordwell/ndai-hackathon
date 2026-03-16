#!/bin/bash
# Launch a Nitro-capable EC2 instance for NDAI
# Usage: ./deploy/launch.sh [region] [key-name]
set -euo pipefail

REGION="${1:-us-east-1}"
KEY_NAME="${2:-}"
INSTANCE_TYPE="c5.xlarge"
AMI=""

echo "=== NDAI EC2 Launch Script ==="
echo "Region: $REGION"
echo "Instance type: $INSTANCE_TYPE"

# Find latest Amazon Linux 2023 AMI
echo "Finding latest AL2023 AMI..."
AMI=$(aws ec2 describe-images \
  --region "$REGION" \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)
echo "AMI: $AMI"

# Create security group if it doesn't exist
SG_NAME="ndai-sg"
SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=group-name,Values=$SG_NAME" \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo "Creating security group..."
  SG_ID=$(aws ec2 create-security-group \
    --region "$REGION" \
    --group-name "$SG_NAME" \
    --description "NDAI application security group" \
    --query 'GroupId' \
    --output text)

  # Allow SSH
  aws ec2 authorize-security-group-ingress \
    --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp --port 22 --cidr 0.0.0.0/0

  # Allow HTTP
  aws ec2 authorize-security-group-ingress \
    --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp --port 80 --cidr 0.0.0.0/0

  # Allow HTTPS
  aws ec2 authorize-security-group-ingress \
    --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp --port 443 --cidr 0.0.0.0/0

  # Allow app port (direct access fallback)
  aws ec2 authorize-security-group-ingress \
    --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp --port 8000 --cidr 0.0.0.0/0

  echo "Security group created: $SG_ID"
else
  echo "Using existing security group: $SG_ID"
fi

# Create key pair if name not provided
if [ -z "$KEY_NAME" ]; then
  KEY_NAME="ndai-key"
  if ! aws ec2 describe-key-pairs --region "$REGION" --key-names "$KEY_NAME" &>/dev/null; then
    echo "Creating key pair..."
    aws ec2 create-key-pair \
      --region "$REGION" \
      --key-name "$KEY_NAME" \
      --query 'KeyMaterial' \
      --output text > "$HOME/.ssh/${KEY_NAME}.pem"
    chmod 600 "$HOME/.ssh/${KEY_NAME}.pem"
    echo "Key saved to ~/.ssh/${KEY_NAME}.pem"
  else
    echo "Using existing key pair: $KEY_NAME"
  fi
fi

# Launch instance
echo "Launching c5.xlarge with Nitro Enclaves enabled..."
INSTANCE_ID=$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --enclave-options Enabled=true \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ndai}]" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance launched: $INSTANCE_ID"
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo ""
echo "=== Instance Ready ==="
echo "Instance ID: $INSTANCE_ID"
echo "Public IP:   $PUBLIC_IP"
echo "SSH:         ssh -i ~/.ssh/${KEY_NAME}.pem ec2-user@${PUBLIC_IP}"
echo ""
echo "Next: run deploy/setup.sh $PUBLIC_IP $KEY_NAME"
