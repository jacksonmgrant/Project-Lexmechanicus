.PHONY: dev backend frontend infra migrate seed fmt sync-knowledge


infra:
	docker compose up -d db redis minio
	@until curl -fsS http://127.0.0.1:9190/minio/health/ready >/dev/null; do \
		echo "Waiting for MinIO on :9190..."; \
		sleep 1; \
	done
	@until docker compose exec -T db pg_isready -U postgres >/dev/null 2>&1; do \
		echo "Waiting for Postgres on :5432..."; \
		sleep 1; \
	done
	@until docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do \
		echo "Waiting for Redis on :6379..."; \
		sleep 1; \
	done


dev: infra
	@trap 'kill 0' INT TERM EXIT; \
	(cd server && set -a && . ../.env && set +a && .venv/bin/python -m uvicorn app.main:app --reload --port 8765) & \
	until curl -fsS http://127.0.0.1:8765/health >/dev/null; do \
		echo "Waiting for backend on :8765..."; \
		sleep 1; \
	done; \
	(cd web && npm run dev) & \
	wait


backend: infra
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
