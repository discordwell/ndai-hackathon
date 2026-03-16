# NDAI Enclave Docker Image
#
# Minimal image for running the negotiation session inside an AWS Nitro Enclave.
# Built with `make enclave-build` and converted to EIF via nitro-cli.
#
# Security notes:
# - No shell access in production (entrypoint is python directly)
# - No network access inside enclave (communication via vsock only)
# - All secrets (API keys) are passed at runtime via vsock, never baked in

FROM python:3.11-slim AS builder

WORKDIR /build

# Install only build-time dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy only what's needed for pip install
COPY pyproject.toml ./
COPY ndai/ ./ndai/

# Install the ndai package with only the dependencies needed inside the enclave.
# We install everything from pyproject.toml, then the image stays small because
# we use a multi-stage build to drop build artifacts.
RUN pip install --no-cache-dir --prefix=/install .

# --- Runtime stage ---
FROM python:3.11-slim

WORKDIR /app

# Install ca-certificates for TLS verification inside enclave (tunnel mode)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy the ndai source (needed for -m invocation)
COPY ndai/ ./ndai/

# Drop to non-root user for defense in depth
RUN useradd --system --no-create-home enclave
USER enclave

# Nitro Enclaves have no network interface; communication is via vsock.
# The enclave app listens on vsock port 5000 (configurable via env).
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python", "-m", "ndai.enclave.app"]
