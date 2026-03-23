# Apache HTTP Server — Verification Target
#
# Reproducible build: same Dockerfile → same Docker image → same EIF → same PCR0
# Seller can build this locally and compare PCR0 against on-chain registry.
#
# Target: Ubuntu 22.04 + Apache httpd
# Oracle: /var/lib/ndai-oracle/ (canary files planted at runtime)
# PoC runs as: unprivileged 'poc' user

# --- Stage 1: Build NDAI Python dependencies with matching Python ---
FROM python:3.10-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY ndai/ ./ndai/
RUN pip install --no-cache-dir --prefix=/install .

# --- Stage 2: Target environment ---
FROM ubuntu:22.04

# Install Apache and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    apache2-utils \
    curl \
    python3 \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && dpkg -s apache2 | grep Version > /VERSIONS.txt \
    && dpkg -s curl | grep Version >> /VERSIONS.txt

# Copy pre-built Python packages from builder (python3.10 matches Ubuntu 22.04)
COPY --from=builder /install/lib/python3.10/site-packages /usr/lib/python3/dist-packages/

# Copy NDAI enclave source
COPY ndai/ /app/ndai/
WORKDIR /app

# Setup oracle dir, poc user, default Apache page
RUN mkdir -p /var/lib/ndai-oracle && chmod 755 /var/lib/ndai-oracle \
    && useradd --system --no-create-home poc \
    && echo '<h1>NDAI Target</h1>' > /var/www/html/index.html \
    && ln -sf /usr/bin/python3 /usr/bin/python

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python3", "-m", "ndai.enclave.app"]
