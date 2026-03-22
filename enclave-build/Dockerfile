# NDAI Enclave Docker Image
#
# Minimal image for running the negotiation session inside an AWS Nitro Enclave.
# Built with `make enclave-build` and converted to EIF via nitro-cli.
#
# IMPORTANT: The runtime stage MUST use amazonlinux:2023 (not python:3.11-slim).
# Debian/Ubuntu-based images crash immediately in Nitro Enclaves due to init
# system incompatibility.
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
RUN pip install --no-cache-dir --prefix=/install .

# --- Runtime stage (Amazon Linux for Nitro Enclave compatibility) ---
FROM amazonlinux:2023

WORKDIR /app

# Install Python 3.11 and ca-certificates for TLS verification
RUN dnf install -y python3.11 ca-certificates shadow-utils && dnf clean all

# Copy installed packages from builder (Python 3.11 site-packages)
COPY --from=builder /install/lib/python3.11/site-packages /usr/lib/python3.11/site-packages/

# Copy the ndai source (needed for -m invocation)
COPY ndai/ ./ndai/

# Note: Running as root inside the enclave. The Nitro Enclave's hardware
# isolation provides the security boundary, not OS-level user separation.
# Root is needed for /dev/nsm access (NSM attestation).

# Nitro Enclaves have no network interface; communication is via vsock.
# The enclave app listens on vsock port 5000 (configurable via env).
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python3.11", "-m", "ndai.enclave.app"]
