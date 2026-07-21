.PHONY: setup dev test test-e2e lint typecheck build migrate

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e 'apps/api[dev]'
	cd apps/api && ../../.venv/bin/alembic upgrade head
	cd apps/web && npm install

dev:
	@echo "Run 'cd apps/api && ../../.venv/bin/uvicorn app.main:app --reload' and 'cd apps/web && npm run dev' in separate terminals."

migrate:
	cd apps/api && ../../.venv/bin/alembic upgrade head

test:
	.venv/bin/pytest apps/api/tests
	cd apps/web && npm test

test-e2e:
	cd apps/web && npm run test:e2e

lint:
	cd apps/api && ../../.venv/bin/ruff check .
	cd apps/web && npm run lint

typecheck:
	cd apps/api && ../../.venv/bin/mypy app
	cd apps/web && npm run typecheck

build:
	cd apps/web && npm run build
