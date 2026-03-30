# Project Cogitator

Cogitator is a FastAPI + React application for searching and querying user-uploaded rules packs. Files are uploaded to S3-compatible storage, normalized into searchable chunks, embedded for later reranking, and then surfaced through keyword search or an SSE-backed answer stream.

> Unofficial fan tool. Not affiliated with any game publisher. Users may only upload material they have the rights to share.

## Stack

- Backend: FastAPI, SQLAlchemy 2 async ORM, Alembic, asyncpg, pgvector, Redis, aioboto3
- Frontend: React, Vite, TypeScript
- Search and retrieval: PostgreSQL full-text search plus pgvector-ready embeddings
- LLM integration: OpenAI Responses API and embeddings
- Storage: S3-compatible object storage such as MinIO

## Repository Layout

```text
.
├── knowledge/              # local staging area for rules, templates, examples, and upload-ready docs
├── server/                 # FastAPI app, Alembic migration, backend package config
│   ├── app/
│   │   ├── routers/        # HTTP endpoints
│   │   ├── services/       # ingestion, retrieval, LLM, parsing helpers
│   │   ├── auth.py         # JWT auth helpers
│   │   ├── config.py       # environment-backed settings
│   │   ├── db.py           # async engine and session factory
│   │   └── models.py       # SQLAlchemy models
│   └── alembic/
├── web/                    # React + Vite frontend
├── docker-compose.yml      # local infra for Postgres, Redis, and MinIO
├── .env.example            # example environment values
└── makefile                # convenience commands
```

## Local Setup

These steps assume macOS or Linux with `git`, Python 3.11+, Node 18+, and Docker available.

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Project-Lexmechanicus
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Review `.env` and update values as needed. For local development, the defaults are intended to work with the included `docker-compose.yml`.

Important values:

- `DATABASE_URL` points to local Postgres with `asyncpg`
- `REDIS_URL` points to Redis used by the rate limiter
- `S3_*` values point to MinIO
- `OPENAI_API_KEY` is required for live answer generation and real embeddings
- `OPENAI_PROJECT_ID` is optional and useful if you want to pin requests to a specific OpenAI project
- `OPENAI_ORG_ID` is optional for org-scoped API setups
- `OPENAI_VECTOR_STORE_ID` is optional and enables hosted OpenAI `file_search` for the ask flow
- `OPENAI_VECTOR_STORE_AUTO_SYNC=1` mirrors app uploads into the configured OpenAI vector store
- `JWT_SECRET` should be changed from the default before sharing an environment

Local document staging:

- Put source rules in `knowledge/rules/`
- Put reusable drafting or prompt assets in `knowledge/templates/`
- Put canonical examples in `knowledge/examples/`
- Use `knowledge/uploads/` as a scratch area for files you are about to upload into the app

### OpenAI dashboard setup

To use the current backend agent flow:

1. Create or choose the OpenAI project you want this app to use.
2. Ensure that project has billing enabled.
3. Create an API key for that project and place it in `.env` as `OPENAI_API_KEY`.
4. If you use project or org scoping in the dashboard, also set `OPENAI_PROJECT_ID` and `OPENAI_ORG_ID`.
5. Create a vector store in the OpenAI dashboard.
6. Copy that vector store ID into `.env` as `OPENAI_VECTOR_STORE_ID`.
7. Leave `OPENAI_VECTOR_STORE_AUTO_SYNC=1` so every new app upload is also mirrored into the hosted vector store.
8. Keep `GPT5_MINI_MODEL`, `GPT5_FULL_MODEL`, and `EMBEDDINGS_MODEL` aligned with models enabled for your project.

If you create a restricted API key in the dashboard, make sure it can read/write the endpoints used by this app:

- `responses`
- `files`
- `vector_stores`
- `embeddings`

With `OPENAI_VECTOR_STORE_ID` unset, the app still works and uses only the app's own retrieval context. With it set, the Responses API can also use OpenAI-hosted `file_search`.

### Sync local knowledge files to OpenAI

The app will automatically mirror new uploads into the configured vector store. To also bulk-sync the local `knowledge/` workspace, run:

```bash
make sync-knowledge
```

That command uploads files from `knowledge/rules/`, `knowledge/templates/`, `knowledge/examples/`, and `knowledge/uploads/` into the same OpenAI vector store used by the ask flow.

### 3. Start local infrastructure

Make sure you do not already have another local PostgreSQL server running on port `5432`. On macOS, if you previously installed Postgres with Homebrew, stop it before starting the Docker database:

```bash
brew services stop postgresql
brew services stop postgresql@16
brew services stop postgresql@18
```

```bash
docker-compose up -d
```

If your Docker installation supports the newer Compose plugin instead, this also works:

```bash
docker compose up -d
```

If either command fails with a Docker socket or daemon error on macOS, Docker Desktop or another Docker runtime is not running yet. Start Docker first, then retry.

This starts:

- PostgreSQL with pgvector on `localhost:5432`
- Redis on `localhost:6379`
- MinIO API on `localhost:9190`
- MinIO console on `http://localhost:9191`

Create the MinIO bucket once the services are up:

1. Open `http://localhost:9191`
2. Sign in with `minioadmin` / `minioadmin`
3. Create a bucket named `cogitator`

### 4. Set up the backend

```bash
cd server
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Use the same interpreter for installs and runtime. If you need to reinstall dependencies later, prefer `python -m pip install -e .` over calling `pip` directly.

Run the database migration:

```bash
set -a
source ../.env
set +a
alembic upgrade head
```

Start the API server:

```bash
set -a
source ../.env
set +a
uvicorn app.main:app --reload --port 8765
```

In a second terminal, from the repository root, you can also use:

```bash
make backend
```

The `make backend` target loads `../.env` automatically and runs Uvicorn from `server/.venv`.

### 5. Set up the frontend

In a new terminal:

```bash
cd web
npm install
npm run dev
```

Or from the repository root:

```bash
make frontend
```

The frontend runs on `http://localhost:4269`.

### 6. Run the full app

If backend and frontend dependencies are already installed, you can run both with:

```bash
make dev
```

This uses:

- `uvicorn app.main:app --reload --port 8765`
- `npm run dev` inside `web/`

The `make dev` target starts both processes together and loads the backend environment automatically.

### 7. Verify the backend is up

```bash
curl http://127.0.0.1:8765/health
```

Expected response:

```json
{"ok": true}
```

## Developer Workflow Notes

### Environment assumptions

The backend reads configuration directly from environment variables in [config.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/config.py). The most important runtime dependencies are:

- Postgres with the `vector` extension enabled
- Redis for rate limiting
- S3-compatible object storage for uploaded files
- OpenAI credentials for real embeddings and answer streaming
- Optional OpenAI vector store access if you want hosted `file_search` inside the Responses API agent flow

If `OPENAI_API_KEY` is missing, answer generation will fail and embeddings fall back to zero vectors.

### Authentication caveat

Most backend routes depend on a bearer token resolved by [auth.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/auth.py). The project includes JWT helper functions, but it does not currently expose a complete public signup/login API in the router layer. If you are standing the app up locally, expect authenticated routes such as `/ask`, `/search`, `/uploads`, and `/viewer` to require a valid bearer token.

### Migrations

Alembic is configured in [alembic.ini](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/alembic.ini). The initial migration creates the core relational tables plus the `file_chunks.embedding` vector column used for reranking.

Apply migrations with:

```bash
cd server
source .venv/bin/activate
set -a
source ../.env
set +a
alembic upgrade head
```

After pulling the vector-store sync changes, make sure you run the migration again so the `files` table can store OpenAI sync IDs and status.

## How the Backend Works

### Request entrypoints

The FastAPI application is defined in [main.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/main.py). It registers four router modules:

- [ask.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/ask.py): streams answers over Server-Sent Events
- [search.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/search.py): keyword search over stored chunks
- [uploads.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/uploads.py): file upload and ingestion
- [viewer.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/viewer.py): byte-range proxy for stored files

There is also a lightweight health check at `/health` and a `/robots.txt` route for crawlers.

### Data model

The SQLAlchemy models live in [models.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/models.py). The main tables are:

- `users`: account records used by JWT auth
- `game_systems`: systems or rulesets a folder belongs to
- `folders`: logical containers for a user's uploaded files
- `files`: stored file metadata and S3 key
- `file_chunks`: normalized text slices extracted from uploaded files

The async database engine and session factory are defined in [db.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/db.py).

### Upload and ingestion pipeline

The upload flow is implemented in [uploads.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/uploads.py):

1. An authenticated user posts a file to `/uploads/`.
2. The raw file is written to S3-compatible storage with `aioboto3`.
3. A `files` row is inserted into Postgres.
4. The file bytes are normalized into plain text via [parsers.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/services/parsers.py).
5. The normalized text is split into overlapping chunks by [chunker.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/services/chunker.py).
6. Each chunk is embedded by [embeddings.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/services/embeddings.py).
7. Chunk rows are stored in `file_chunks` for later retrieval.

Today this ingestion path runs inline during the request. That keeps the flow simple, but it also means large uploads will tie up the request until parsing, chunking, and embedding finish.

### Search flow

[search.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/search.py) runs a Postgres full-text search query against `file_chunks.snippet`. It filters results by `game_system_id` through the `files` and `folders` relationship and returns short previews for the UI.

This route is intentionally keyword-first. It does not depend on an external search engine.

### Ask flow

[ask.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/ask.py) powers the streamed answer experience:

1. The request is authenticated.
2. The rate limiter checks per-user limits using Redis through [rate_limiter.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/rate_limiter.py).
3. The app retrieves relevant chunks through [retrieval.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/services/retrieval.py).
4. The model is chosen by [model_router.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/services/model_router.py), which can escalate from `gpt-5-mini` to `gpt-5`.
5. The answer is streamed from [openai_llm.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/services/openai_llm.py) as SSE `token` events.

The retrieval layer is currently hybrid-ready, but the live implementation is still weighted toward Postgres full-text search. Vector reranking is scaffolded and the schema supports it.

### File viewing

[viewer.py](/Users/jacksongrant/Personal/Project-Lexmechanicus/server/app/routers/viewer.py) fetches the original uploaded file from S3-compatible storage and returns it to the client. It supports byte-range requests so the frontend can deep-link to a location inside a stored file.

### Current backend limitations

Developers working in this repo should be aware of a few current edges:

- auth helpers exist, but a full auth API is not wired into routers yet
- upload authorization and public/private visibility checks are still partial
- retrieval comments note that user-scope filtering should be tightened further
- ingestion is synchronous and should eventually move to background work

## Useful Commands

From the repository root:

```bash
make dev
make backend
make frontend
make migrate
```

## Legal Notes

- Only index content that users are licensed or permitted to upload
- Public sharing of copyrighted text should be treated cautiously
- If you add marketplace or sharing features, keep takedown and purge paths in mind
