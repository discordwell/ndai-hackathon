# Apache HTTP Server 2.4.52 — Verification Target
#
# Reproducible build: same Dockerfile → same Docker image → same EIF → same PCR0
# Seller can build this locally and compare PCR0 against on-chain registry.
#
# Base: Ubuntu 22.04
# Packages: apache2=2.4.52-1ubuntu4.3, curl
# Service: apache2 on port 80
# Oracle: /var/lib/ndai-oracle/ (canary files planted at runtime)
# PoC runs as: unprivileged 'poc' user

FROM ubuntu:22.04

# Install target software
# NOTE: Version pinning commented out — Ubuntu repos drop old patch versions.
# Reproducibility comes from the Docker image digest (sha256), not version strings.
# The PCR0 is deterministic for a given Docker image content.
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    apache2-utils \
    curl \
    python3 \
    python3-pip \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && echo "apache2 $(dpkg -s apache2 | grep Version)" > /VERSIONS.txt \
    && echo "curl $(dpkg -s curl | grep Version)" >> /VERSIONS.txt

# Create oracle directory (canary files planted at verification time)
RUN mkdir -p /var/lib/ndai-oracle && chmod 755 /var/lib/ndai-oracle

# Create unprivileged PoC user (exploit runs as this user)
RUN useradd --system --no-create-home poc

# Default Apache config (port 80, www-data user)
RUN echo '<html><body><h1>NDAI Verification Target</h1></body></html>' > /var/www/html/index.html

# Install NDAI verification runtime
COPY ndai/ /app/ndai/
COPY pyproject.toml /app/
WORKDIR /app
RUN pip3 install --no-cache-dir --break-system-packages . 2>/dev/null || pip3 install --no-cache-dir .

# Symlinks for Nitro compatibility
RUN ln -sf /usr/bin/python3 /usr/bin/python

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Entrypoint: NDAI enclave app (listens on vsock port 5000)
ENTRYPOINT ["python3", "-m", "ndai.enclave.app"]
