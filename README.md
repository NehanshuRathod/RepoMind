# Repomind

Repomind is an AI-powered semantic code search backend. It lets a developer create projects, index a GitHub repository or uploaded ZIP file, and ask natural-language questions such as "where is authentication handled?" or "which function builds embeddings?". Instead of only matching exact keywords, Repomind converts code and queries into vector embeddings and uses FAISS to find code chunks with similar meaning.

The project is built as a FastAPI service with authentication, project ownership, repository indexing, vector search, metadata storage, and chat history. It is designed as a lightweight backend foundation for tools similar in spirit to Sourcegraph, GitHub Code Search, and code-understanding assistants.

## Why This Project Is Useful

Large repositories are hard to understand when you do not already know file names, function names, or exact keywords. Traditional search works well when you know what to type, but it struggles with intent-based questions.

Repomind solves that by indexing code semantically:

- It breaks source files into meaningful code chunks, such as Python classes and functions.
- It embeds those chunks using a sentence-transformer model.
- It stores the vectors in a FAISS index for fast similarity search.
- It stores metadata such as file path, class name, function name, line numbers, language, and snippet preview.
- It lets users search with natural language and receive relevant code locations.

This makes the system useful for onboarding into a new repository, exploring unfamiliar code, building AI developer tools, and demonstrating practical ML infrastructure skills.

## Current Features

- User registration and login
- Password hashing with salted PBKDF2-HMAC
- JWT-based protected APIs
- Project creation, listing, refresh, and deletion
- GitHub repository cloning
- ZIP repository upload and safe extraction
- Temporary repository workspaces with cleanup after indexing
- File loading and filtering for common programming languages
- Python AST parsing
- Function, async function, method, and class chunk extraction for Python
- Batch embeddings with `sentence-transformers/all-MiniLM-L6-v2`
- Singleton model loading so the embedding model is not reloaded per request
- Normalized vectors for cosine-style similarity search
- FAISS vector index persistence per project
- SQLAlchemy metadata storage
- Per-project chat history
- Optional Celery and Redis wiring for queued refresh tasks
- Docker and Docker Compose setup
- GitHub Actions CI for tests

## How Repomind Works

At a high level, Repomind has two main workflows: indexing and searching.

### 1. Indexing Workflow

When a user creates or uploads a project, Repomind prepares the repository and turns source code into searchable vector data.

```text
GitHub URL or ZIP upload
    -> RepositoryManager
    -> FileLoader
    -> FileFilter
    -> ASTParser
    -> ChunkExtractor
    -> EmbeddingService
    -> FaissStore
    -> SQL metadata tables
```

The important steps are:

1. Repository input
   - GitHub projects are cloned into a temporary workspace.
   - ZIP uploads are safely extracted into a temporary workspace.
   - Temporary source files are deleted after indexing.

2. File discovery
   - The file loader recursively finds files in the workspace.
   - The file filter ignores directories such as `.git`, `node_modules`, `venv`, `__pycache__`, `dist`, `build`, and `target`.
   - It accepts common code extensions such as `.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`, `.cpp`, and `.c`.

3. Code parsing and chunking
   - Python files are parsed with Python's built-in `ast` module.
   - Repomind extracts classes, functions, async functions, and methods.
   - Each chunk keeps its file path, name, class name, function name, start line, end line, language, content hash, and source snippet.

4. Embedding generation
   - Each code chunk is passed to the sentence-transformer model.
   - Embeddings are generated in batches.
   - Vectors are normalized before storage.

5. Vector and metadata storage
   - FAISS stores the numeric vectors for similarity search.
   - SQLite stores project records, file hashes, chunk metadata, and chat history.
   - Each project has its own isolated FAISS index file.

### 2. Search Workflow

When a user asks a question, Repomind embeds the question and compares it against the indexed code vectors.

```text
User query
    -> query embedding
    -> FAISS similarity search
    -> metadata lookup
    -> ranked response
```

The response includes useful developer-facing details:

- Project ID
- File path
- Function name
- Class name
- Similarity score
- Start line
- End line
- Snippet preview

This means the user does not just get a vague answer. They get concrete code locations that can be opened and inspected.

## Machine Learning and Vector Search

Repomind uses practical ML infrastructure rather than training a model from scratch.

### Embedding Model

The default model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

This model converts natural language and text-like code snippets into dense numeric vectors. Similar meanings tend to produce vectors that are close together.

Example idea:

```text
"login user with password"
```

can match code that contains:

```python
def authenticate(email: str, password: str):
    ...
```

Even if the exact words are not identical, the embedding model can still place related concepts near each other in vector space.

### Singleton Model Loading

Loading an embedding model is expensive. Repomind keeps the model as a process-level singleton inside `EmbeddingService`, protected by a lock. This prevents the app from reloading the model for every request.

### Batch Embeddings

During indexing, code chunks are embedded as a batch. Batch embedding is much faster and more production-friendly than embedding one chunk at a time.

### FAISS

FAISS is used as the vector search engine. Repomind currently uses a flat inner-product index with normalized vectors, which behaves like cosine similarity.

This is simple, accurate, and good for a first production milestone. The architecture can later support larger FAISS index types such as HNSW or IVF for very large repositories.

## Backend Architecture

Repomind keeps API routing separate from business logic.

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

### Layer Responsibilities

API layer:

- Defines HTTP endpoints
- Validates request and response schemas
- Injects database sessions and authenticated users
- Delegates business logic to services

Service layer:

- Handles registration and login
- Manages projects and ownership
- Runs indexing workflows
- Runs semantic search
- Stores chat history

Indexing layer:

- Clones or extracts repositories
- Loads files
- Filters unsupported or generated files
- Parses Python files
- Extracts semantic chunks

Vector layer:

- Loads the embedding model
- Generates embeddings
- Creates, saves, loads, searches, and deletes FAISS indexes

Metadata layer:

- Defines SQLAlchemy database tables
- Stores users, projects, files, chunks, and chat messages

## Database Design

The default database is SQLite for local development and simple deployment.

Main tables:

- `users`
- `projects`
- `files`
- `embeddings_metadata`
- `chat_history`

Important stored metadata includes:

- User ID
- Project ID
- Repository URL
- Commit hash
- FAISS index path
- File path
- Language
- Class name
- Function name
- Start and end lines
- Chunk hash
- Snippet preview

The source repository itself is not permanently stored. Only embeddings and metadata are persisted.

## Security Notes

Repomind includes the security basics expected from a backend service:

- Passwords are never stored in plaintext.
- Passwords are hashed using salted PBKDF2-HMAC SHA-256.
- Login returns a JWT access token.
- Project APIs require authentication.
- Project lookup validates ownership so users cannot access another user's project.
- Uploaded ZIP files are checked for unsafe paths before extraction.
- `.env` is ignored by git.

The README shows example environment variable values only. Never commit real secrets, real tokens, or production credentials.

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

SQLite is the default. PostgreSQL can be introduced later by changing `DATABASE_URL` and installing the correct PostgreSQL driver.

## Local Setup

Create and activate a virtual environment:

```bash
python -m venv venv
```

On Windows:

```powershell
venv\Scripts\activate
```

On macOS or Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the API:

```bash
python -m uvicorn app.main:app --reload
```

Open the interactive API docs:

```text
http://127.0.0.1:8000/docs
```

## API Usage Flow

1. Register a user

```http
POST /auth/register
```

Body:

```json
{
  "email": "developer@example.com",
  "password": "Password123!",
  "full_name": "Developer"
}
```

2. Login

```http
POST /auth/login
```

This endpoint uses OAuth2 form fields:

```text
username=developer@example.com
password=Password123!
```

3. Create and index a GitHub project

```http
POST /projects
```

Body:

```json
{
  "project_name": "fastapi-demo",
  "repo_url": "https://github.com/example/example-repo.git"
}
```

4. Upload and index a ZIP project

```http
POST /projects/upload?project_name=my-uploaded-project
```

Upload a `.zip` file as multipart form data.

5. Search a project

```http
POST /projects/{project_id}/search
```

Body:

```json
{
  "query": "where is authentication implemented?",
  "top_k": 5
}
```

6. Read chat history

```http
GET /projects/{project_id}/chat
```

7. Delete a project

```http
DELETE /projects/{project_id}
```

Deleting a project removes database records and the related FAISS index file.

## Background Workers

Repomind includes Celery wiring for queued project refresh tasks.

Start Redis, then run:

```bash
celery -A app.tasks.indexing_tasks worker --loglevel=INFO
```

Redis is configured through `REDIS_URL`, defaulting to:

```text
redis://localhost:6379/0
```

The current API path performs indexing synchronously. The Celery integration is ready for async job orchestration and progress endpoints in a later milestone.

## Docker

Build and run the API with Redis:

```bash
docker compose up --build
```

The compose setup starts:

- FastAPI application
- Redis
- Persistent Docker volume for local app data

## Tests

Run tests with:

```bash
python -m pytest
```

The test suite currently covers:

- Python AST chunk extraction
- File filtering
- FAISS save, load, and search
- Password hashing and verification

## Current Limitations

This is a strong backend milestone, but it is not the final version of every feature in the original product vision.

Current limitations:

- Semantic chunk extraction is implemented for Python first.
- Other language files are discovered and tracked as file metadata, but deep AST chunking for JavaScript, TypeScript, Java, Go, Rust, and C++ is future work.
- Indexing currently runs synchronously from the API path.
- Celery is wired, but full job status, progress tracking, and retry dashboards are future work.
- Refresh currently rebuilds the project index instead of doing a fully incremental chunk-level update.
- There is no frontend yet.
- The search response returns relevant code locations and snippets; it does not yet generate a natural-language answer with an LLM.

## Future Improvements

Good next steps:

- Add Tree-sitter parsers for multiple languages.
- Add true incremental indexing based on changed and removed file hashes.
- Add async indexing endpoints with job status and progress reporting.
- Add Redis caching for repeated queries and project metadata.
- Add PostgreSQL support for production deployments.
- Add a frontend for project management and search.
- Add result reranking for better search quality.
- Add observability metrics for indexing duration, search latency, and error rates.
- Add more integration tests around auth, project ownership, and upload indexing.

## Why This Is a Good Portfolio Project

Repomind demonstrates several real-world engineering skills in one system:

- API design with FastAPI
- Authentication and authorization
- Clean service-layer architecture
- Repository ingestion and temporary file cleanup
- Static code parsing with ASTs
- Practical ML model usage with sentence transformers
- Vector search with FAISS
- Metadata modeling with SQLAlchemy
- Docker-based deployment setup
- CI testing with GitHub Actions
- Future-ready architecture for queues, caching, and multi-language parsing

It is not just a CRUD app. It combines backend engineering, ML infrastructure, code intelligence, and search systems in a way that is easy to explain and extend.
