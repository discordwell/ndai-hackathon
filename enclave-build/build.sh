#!/bin/bash
# Build the NDAI enclave Docker image and convert to EIF.
# Requires: docker
# Optional: nitro-cli (only available on Nitro-capable EC2 instances)
#
# Usage:
#   make enclave-build          # from project root
#   ./enclave-build/build.sh    # directly
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

IMAGE_NAME="ndai-enclave"
EIF_OUTPUT="$PROJECT_ROOT/ndai_enclave.eif"

echo "==> Building enclave Docker image: $IMAGE_NAME"
docker build \
    -t "$IMAGE_NAME" \
    -f "$SCRIPT_DIR/Dockerfile" \
    "$PROJECT_ROOT"

echo "==> Docker image built successfully"
docker images "$IMAGE_NAME:latest" --format "Size: {{.Size}}"

# Convert to EIF if nitro-cli is available
if command -v nitro-cli &>/dev/null; then
    echo "==> Converting Docker image to EIF"
    nitro-cli build-enclave \
        --docker-uri "$IMAGE_NAME:latest" \
        --output-file "$EIF_OUTPUT"

    echo "==> EIF built: $EIF_OUTPUT"
    echo ""
    echo "PCR values (record these for attestation verification):"
    nitro-cli describe-eif --eif-path "$EIF_OUTPUT"
    echo ""
    echo "To run the enclave:"
    echo "  nitro-cli run-enclave --cpu-count 2 --memory 1600 --eif-path $EIF_OUTPUT"
else
    echo ""
    echo "==> nitro-cli not found"
    echo "    Docker image built but EIF conversion requires a Nitro-capable EC2 instance."
    echo "    Supported instances: c5.xlarge, m5.xlarge, r5.xlarge, or larger."
    echo ""
    echo "    To install nitro-cli on Amazon Linux 2:"
    echo "      sudo amazon-linux-extras install aws-nitro-enclaves-cli"
    echo "      sudo yum install aws-nitro-enclaves-cli-devel"
    echo ""
    echo "    Then re-run: make enclave-build"
fi
