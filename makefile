.PHONY: dev backend frontend migrate seed fmt sync-knowledge


dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd server && set -a && . ../.env && set +a && .venv/bin/python -m uvicorn app.main:app --reload --port 8765) & \
	(cd web && npm run dev) & \
	wait


backend:
	cd server && set -a && . ../.env && set +a && .venv/bin/python -m uvicorn app.main:app --reload --port 8765


frontend:
	cd web && npm run dev


migrate:
	cd server && set -a && . ../.env && set +a && .venv/bin/python -m alembic upgrade head


seed:
	cd server && python -m app.scripts.seed


fmt:
	cd server && ruff check --fix . && black .


sync-knowledge:
	cd server && set -a && . ../.env && set +a && .venv/bin/python scripts/sync_openai_vector_store.py
