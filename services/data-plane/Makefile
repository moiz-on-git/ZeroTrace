# ZeroTrace Data Plane Makefile
# Usage: make up | make seed | make reset | make test | make demo | make prod-build

.PHONY: up down seed reset test demo lint typecheck install openapi \
        prod-build prod-up prod-down migrate migrate-up \
        load-test clean

COMPOSE_FILE = docker-compose.dataplane.yml
PROFILE      ?= small
BASE_URL     ?= http://localhost:8002
SERVICE_KEY  ?= zt-dev-service-key-2026

# ── Docker ───────────────────────────────────────────────────────────────────
up:
	docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@docker compose -f $(COMPOSE_FILE) ps

down:
	docker compose -f $(COMPOSE_FILE) down

logs:
	docker compose -f $(COMPOSE_FILE) logs -f data-plane

# ── Production Docker ────────────────────────────────────────────────────────
prod-build:
	docker build -t zerotrace-data-plane:prod -f Dockerfile .
	@echo "Production image built: zerotrace-data-plane:prod"

prod-up:
	docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "Production stack running"

prod-down:
	docker compose -f $(COMPOSE_FILE) down -v
	@echo "Production stack stopped (volumes removed)"

# ── Database migrations ──────────────────────────────────────────────────────
migrate:
	alembic upgrade head
	@echo "Migrations applied"

migrate-up:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migrate-new:
	alembic revision --autogenerate -m "$(MSG)"

# ── Install (local dev without Docker) ───────────────────────────────────────
install:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt
	python -m pip install "sqlalchemy[asyncio]" asyncpg greenlet

# ── Seed and Reset ───────────────────────────────────────────────────────────
seed:
	curl -s -X POST $(BASE_URL)/v1/demo/seed \
	  -H "X-Service-Key: $(SERVICE_KEY)" \
	  -H "Content-Type: application/json" \
	  -d '{"profile": "$(PROFILE)"}' | python -m json.tool

reset:
	curl -s -X POST $(BASE_URL)/v1/demo/reset \
	  -H "X-Service-Key: $(SERVICE_KEY)" | python -m json.tool

# ── Demo ─────────────────────────────────────────────────────────────────────
demo:
	python scripts/demo_cli.py --profile $(PROFILE) --base-url $(BASE_URL)

# ── Tests ────────────────────────────────────────────────────────────────────
test:
	python -m pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

test-unit:
	python -m pytest tests/test_seed_determinism.py tests/test_bloom_index.py \
	  tests/test_attack_masking.py tests/test_planner.py tests/test_retention_vault.py \
	  tests/test_ghost_embedding.py tests/test_pii_redaction.py tests/test_idempotency.py \
	  tests/test_prod_hardening.py tests/test_api_health.py -v

test-api:
	python -m pytest tests/test_api_health.py tests/test_prod_hardening.py -v

test-integration:
	python -m pytest tests/test_cache_eraser.py -v

# ── Load testing (requires k6) ────────────────────────────────────────────────
load-test:
	@echo "Running k6 load test against $(BASE_URL)..."
	k6 run tests/load/k6_load_test.js --env BASE_URL=$(BASE_URL) --env SERVICE_KEY=$(SERVICE_KEY)

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	python -m ruff check src/ tests/ scripts/

lint-fix:
	python -m ruff check --fix src/ tests/ scripts/

typecheck:
	python -m mypy src/ --ignore-missing-imports

# ── OpenAPI export ────────────────────────────────────────────────────────────
openapi:
	python -c "
import json, sys
sys.path.insert(0, '.')
from src.main import app
print(json.dumps(app.openapi(), indent=2))
" > openapi.json
	@echo "OpenAPI spec written to openapi.json"

# ── Health check ─────────────────────────────────────────────────────────────
health:
	@echo "Liveness:"
	curl -s $(BASE_URL)/live | python -m json.tool
	@echo "\nReadiness:"
	curl -s $(BASE_URL)/ready | python -m json.tool
	@echo "\nDeep health:"
	curl -s -H "X-Service-Key: $(SERVICE_KEY)" $(BASE_URL)/v1/health/deep | python -m json.tool
	@echo "\nMetrics:"
	curl -s $(BASE_URL)/metrics | head -20

# ── Clean ──────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -f test_results.txt prod_test_results.txt final_test_results.txt
	@echo "Cleaned"
