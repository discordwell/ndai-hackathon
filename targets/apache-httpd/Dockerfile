# Apache HTTP Server — Verification Target
#
# Built on the same pattern as enclave-build/Dockerfile (which works in Nitro).
# Adds httpd to the base amazonlinux:2023 + python3.11 image.

FROM python:3.11-slim AS builder

WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
COPY pyproject.toml ./
COPY ndai/ ./ndai/
RUN pip install --no-cache-dir --prefix=/install .

# --- Runtime: Amazon Linux (Nitro-compatible) + Apache httpd ---
FROM amazonlinux:2023

WORKDIR /app

# Install Python 3.11, Apache httpd, and utilities
RUN dnf install -y --allowerasing python3.11 httpd curl procps-ng shadow-utils && dnf clean all \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

# Copy installed Python packages from builder
COPY --from=builder /install/lib/python3.11/site-packages /usr/lib/python3.11/site-packages/

# Copy NDAI source
COPY ndai/ ./ndai/

# Setup target environment
RUN mkdir -p /var/lib/ndai-oracle && chmod 755 /var/lib/ndai-oracle \
    && useradd --system --no-create-home poc \
    && echo '<h1>NDAI Target — Apache httpd</h1>' > /var/www/html/index.html \
    && rpm -q httpd > /VERSIONS.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python3.11", "-m", "ndai.enclave.app"]
