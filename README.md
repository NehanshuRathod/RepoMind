# Repomind

Repomind is a FastAPI semantic code search backend for indexing repositories and answering natural-language code questions. It supports authenticated users, per-user projects, GitHub repository indexing, ZIP upload indexing, FAISS vector search, metadata storage in SQLite, and per-project chat history.

## Architecture

Request flow is intentionally layered:

- API routers validate and orchestrate requests.
- Services own business logic for auth, project management, indexing, and search.
- Indexing modules clone or extract repositories, load and filter files, parse Python ASTs, and extract function/class chunks.
- `EmbeddingService` loads `sentence-transformers/all-MiniLM-L6-v2` once per process and embeds batches.
- `FaissStore` persists one isolated FAISS index per project.
- SQLAlchemy stores users, projects, file hashes, chunk metadata, and chat history.

Source repositories are kept only in temporary workspaces and are deleted after indexing. The persistent state is the vector index plus database metadata.

## Folder Structure

```text
app/
  api/              FastAPI routers, schemas, dependencies
  core/             settings, database, security, Celery app
  indexing/         repository loading, filtering, AST parsing, chunk extraction
  metadata/         SQLAlchemy ORM models
  search/           reserved for future search adapters
  services/         business logic layer
  tasks/            Celery tasks
  vectorstore/      embeddings and FAISS persistence
  main.py           FastAPI application
```

## Local Setup

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API docs.

## Core API Flow

1. `POST /auth/register` with `email`, `password`, and optional `full_name`.  
2. `POST /auth/login` using OAuth2 form fields `username` and `password`.
3. Authorize with the returned bearer token.
4. `POST /projects` with `project_name` and optional `repo_url` to create and index a GitHub project.
5. `POST /projects/upload?project_name=...` with a ZIP file to index an upload.
6. `POST /projects/{project_id}/search` with `query` and `top_k`.
7. `GET /projects/{project_id}/chat` to read project chat history.
8. `DELETE /projects/{project_id}` to delete metadata and the FAISS index.

## Background Workers

A Celery task is available for queued refreshes:

```bash
celery -A app.tasks.indexing_tasks worker --loglevel=INFO
```

Redis is configured through `REDIS_URL`, defaulting to `redis://localhost:6379/0`.

## Environment Variables

```env
APP_DEBUG=true
DATABASE_URL=sqlite:///./storage/repomind.db
SECRET_KEY=replace-with-a-long-random-value
VECTOR_STORE_DIR=storage/vector_indexes
UPLOAD_DIR=storage/uploads
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
REDIS_URL=redis://localhost:6379/0
```

SQLite is the default. PostgreSQL can be introduced later by changing `DATABASE_URL` and installing an appropriate driver.

## Tests

```bash
pytest
```

The FAISS test automatically skips if `faiss-cpu` is not installed.

## Docker

```bash
docker compose up --build
```

The compose stack starts the API and Redis. Add a worker service using the documented Celery command when queued refresh workers are needed.
    


