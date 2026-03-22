# TrustKit — multi-platform TEE application
# Works on: bare metal, AWS Nitro, dstack (Intel TDX)
#
# Build: docker build -t trustkit .
# Run locally: docker compose up
# Deploy to dstack: dstack deploy dstack-compose.yaml

FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Node.js for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml setup.cfg setup.py ./
RUN pip install --no-cache-dir -e ".[dev]" dstack-sdk 2>/dev/null || pip install --no-cache-dir -e . dstack-sdk

# Frontend build
COPY frontend/ frontend/
RUN cd frontend && npm install --silent && npm run build

# App code
COPY ndai/ ndai/
COPY alembic/ alembic/
COPY alembic.ini .

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn ndai.api.app:create_app --factory --host 0.0.0.0 --port 8100 --workers 1"]

EXPOSE 8100
