# Apache HTTP Server — Verification Target
#
# Reproducible build: same Dockerfile → same Docker image → same EIF → same PCR0
# Seller can build this locally and compare PCR0 against on-chain registry.
#
# Uses the same base as the main enclave (amazonlinux:2023) for Nitro compat.
# Apache httpd is installed via the Amazon Linux repos.

# --- Stage 1: Build NDAI Python dependencies ---
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY ndai/ ./ndai/
RUN pip install --no-cache-dir --target=/install .

# --- Stage 2: Amazon Linux + Apache + NDAI runtime ---
FROM amazonlinux:2023

# Install Python 3.11, Apache httpd, and utilities
RUN dnf install -y \
    python3.11 \
    httpd \
    curl \
    procps-ng \
    shadow-utils \
    ca-certificates \
    && dnf clean all \
    && rpm -q httpd | tee /VERSIONS.txt

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/lib/python3.11/site-packages/

# Copy NDAI enclave source
COPY ndai/ /app/ndai/
WORKDIR /app

# Setup oracle dir, poc user, default page, symlinks
RUN mkdir -p /var/lib/ndai-oracle && chmod 755 /var/lib/ndai-oracle \
    && useradd --system --no-create-home poc \
    && echo '<h1>NDAI Target — Apache httpd</h1>' > /var/www/html/index.html \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python3.11", "-m", "ndai.enclave.app"]
