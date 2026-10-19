.PHONY: up down test test-conformance bench load e2e seed reset demo docker-build clean help

help:
	@echo "=================================================================="
	@echo "ZeroTrace Monorepo Build & Operations Commands"
	@echo "=================================================================="
	@echo "  make up               Start local docker stack (orchestrator, minio, postgres, redis)"
	@echo "  make down             Stop local stack and remove volumes"
	@echo "  make test             Run full 48-test orchestrator & contract test suite"
	@echo "  make test-conformance Run OpenAPI 3.0 contract conformance tests"
	@echo "  make bench            Run sub-second Merkle and Ed25519 proof benchmarks"
	@echo "  make load             Run 50-client asynchronous load & SLO validation test"
	@echo "  make e2e              Run 10-stage headless golden path pipeline test"
	@echo "  make seed             Seed 50,000 customers & 480 Parquet lakehouse files"
	@echo "  make reset            Reset demo state to clean baseline"
	@echo "  make demo             Run Demo Director interactive CLI (golden scenario)"
	@echo "  make demo-ghost       Run Demo Director self-healing ghost embedding scenario"
	@echo "  make demo-hold        Run Demo Director statutory retention hold scenario"
	@echo "  make docker-build     Build production orchestrator Docker image"
	@echo "  make clean            Clean temporary test caches and local databases"

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down -v

test:
	pytest services/orchestrator/tests -v

test-conformance:
	pytest services/orchestrator/tests/test_contract_conformance.py -v

bench:
	python scripts/benchmark_proofs.py

load:
	python scripts/load_test.py

e2e:
	python scripts/e2e_golden_path.py

seed:
	curl -s -X POST http://localhost:8001/api/v1/demo/seed -H "Content-Type: application/json" -d "{\"profile\":\"showtime\"}"

reset:
	curl -s -X POST http://localhost:8001/api/v1/demo/reset

demo:
	python demo/director/scenario_runner.py --scenario golden

demo-ghost:
	python demo/director/scenario_runner.py --scenario ghost_heal

demo-hold:
	python demo/director/scenario_runner.py --scenario retention_hold

docker-build:
	docker build -t zerotrace-orchestrator:latest -f services/orchestrator/Dockerfile .

clean:
	python -c "import shutil, glob, os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/.pytest_cache', recursive=True)]; [os.remove(f) for f in glob.glob('*.db') if os.path.exists(f)]"
