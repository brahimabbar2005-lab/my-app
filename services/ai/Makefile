.PHONY: help install build run test eval eval-gate eval-full eval-model check-model lint sync purge clean

help:
	@echo "install     install dependencies"
	@echo "build       rebuild the knowledge base from data/source/*.xlsx"
	@echo "run         start the API on http://localhost:8000"
	@echo "test        run the test suite (no API key needed)"
	@echo "eval        offline evaluation over the golden set (no API key needed)"
	@echo "eval-gate   fail if eval scores drop below eval/baseline.json"
	@echo "check-model one real request to confirm the key and model work"
	@echo "eval-model  evaluation with real answers (uses model requests)"
	@echo "lint        ruff"
	@echo "sync        pull content from WordPress and reindex"
	@echo "purge       apply the conversation retention policy"

install:
	@python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 'Python 3.11+ required, found ' + sys.version.split()[0])"
	pip install --upgrade pip
	pip install -r requirements-dev.txt

build:
	python scripts/generate_affiliate_map.py && mv -f 07_AFFILIATE_MAP.xlsx data/source/ 2>/dev/null || true
	python scripts/build_knowledge_base.py

run:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -q

eval:
	python -m eval.harness --offline --full

eval-gate:
	-python -m eval.harness --offline --full > /dev/null
	python scripts/check_eval_baseline.py

check-model:
	python scripts/check_model.py

eval-model:
	python -m eval.harness --limit 30 --rubric

eval-full:
	python -m eval.harness --full --rubric --concurrency 4

lint:
	ruff check app scripts eval tests

sync:
	python scripts/wp_sync.py

purge:
	curl -s -X POST localhost:8000/api/admin/purge -H "X-Admin-Key: $$ADMIN_KEY"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
