# Apache HTTP Server — Verification Target
#
# Reproducible build: same Dockerfile → same Docker image → same EIF → same PCR0
# Seller can build this locally and compare PCR0 against on-chain registry.
#
# Target: Ubuntu 22.04 + Apache httpd
# Oracle: /var/lib/ndai-oracle/ (canary files planted at runtime)
# PoC runs as: unprivileged 'poc' user

# --- Stage 1: Build NDAI Python dependencies ---
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY ndai/ ./ndai/
RUN pip install --no-cache-dir --target=/install .

# --- Stage 2: Target environment ---
FROM ubuntu:22.04

# Install Apache, Python 3.11 (deadsnakes PPA), and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    apache2-utils \
    curl \
    software-properties-common \
    ca-certificates \
    procps \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3.11 \
    && rm -rf /var/lib/apt/lists/* \
    && dpkg -s apache2 | grep Version > /VERSIONS.txt \
    && dpkg -s curl | grep Version >> /VERSIONS.txt

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local/lib/python3.11/dist-packages/

# Copy NDAI enclave source
COPY ndai/ /app/ndai/
WORKDIR /app

# Setup oracle dir, poc user, default Apache page, symlinks
RUN mkdir -p /var/lib/ndai-oracle && chmod 755 /var/lib/ndai-oracle \
    && useradd --system --no-create-home poc \
    && echo '<h1>NDAI Target</h1>' > /var/www/html/index.html \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/usr/local/lib/python3.11/dist-packages

ENTRYPOINT ["python3.11", "-m", "ndai.enclave.app"]
