.PHONY: install dev test lint format migrate run infra infra-down enclave-build frontend-install frontend-build frontend-dev

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/

test-cov:
	pytest tests/ --cov=ndai --cov-report=html

lint:
	ruff check ndai/ tests/
	mypy ndai/

format:
	ruff format ndai/ tests/
	ruff check --fix ndai/ tests/

migrate:
	alembic upgrade head

run:
	uvicorn ndai.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000

infra:
	docker compose up -d

infra-down:
	docker compose down

enclave-build:
	cd enclave-build && ./build.sh

frontend-install:
	cd frontend && npm install

frontend-build:
	cd frontend && npm run build

frontend-dev:
	cd frontend && npm run dev
