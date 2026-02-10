# Project Conventions

## Database Migrations

Always use [golang-migrate/migrate](https://github.com/golang-migrate/migrate) to create new migrations:

```bash
migrate create -ext sql -dir backend/migrations -seq <migration_name>
```

This creates properly formatted migration files with sequential numbering.

### Always add table and column descriptions

Every migration that creates a table or adds a column must include `COMMENT ON` statements. This provides self-documenting schema metadata that helps AI tools, new developers, and database GUIs understand the data model:

```sql
-- When creating a table
CREATE TABLE IF NOT EXISTS documents (...);
COMMENT ON TABLE documents IS 'Ingested PDF documents with deduplication via content hash';
COMMENT ON COLUMN documents.file_hash IS 'SHA-256 hash of file contents for deduplication';

-- When adding a column
ALTER TABLE chunks ADD COLUMN bbox JSONB;
COMMENT ON COLUMN chunks.bbox IS 'Bounding box coordinates on the page as JSON {x0, y0, x1, y1}';
```

## Repository Structure

This is a monorepo with the following layout:

- `backend/` — Python FastAPI server, migrations, tests, scripts
- `frontend/` — React/TanStack Router app (TypeScript, TailwindCSS)
- Root — Infrastructure and config files (docker-compose.yaml, Taskfile.yml, CLAUDE.md, etc.)

## Database Patterns (psycopg2)

When writing database code with psycopg2, follow these patterns:

### 1. Import everything you use explicitly

```python
from psycopg2.extras import Json, RealDictCursor, execute_values
```

Do NOT use `psycopg2.extras.Json` inline - import it directly.

### 2. Always handle transaction rollback on failure

Every method that calls `commit()` must wrap the operation in try-except and rollback on failure:

```python
def insert_something(self, data):
    try:
        with self.conn.cursor() as cur:
            cur.execute("INSERT ...", (data,))
        self.conn.commit()
        return result
    except Exception:
        self.conn.rollback()
        raise
```

This prevents leaving the connection in an error state that breaks subsequent operations.

### 3. Use batch inserts for performance

Never insert rows one-by-one in a loop. Use `execute_values()` for batch inserts:

```python
# BAD - N database round-trips
for item in items:
    cur.execute("INSERT INTO table VALUES (%s)", (item,))

# GOOD - single round-trip
from psycopg2.extras import execute_values
values = [(item,) for item in items]
execute_values(cur, "INSERT INTO table VALUES %s RETURNING *", values, fetch=True)
```

### 4. Use RealDictCursor for readable results

```python
with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("SELECT * FROM table")
    row = cur.fetchone()  # Returns dict with column names as keys
```

## Resource Cleanup

### Always use try-finally for file handles and external resources

When opening files, documents, or other resources that need cleanup, always use try-finally to ensure the resource is closed even if an exception occurs:

```python
# GOOD - resource is always closed
doc = fitz.open(file_path)
try:
    # all processing logic here
    result = process_document(doc)
    return result
finally:
    doc.close()

# BAD - resource leaks if exception occurs before close()
doc = fitz.open(file_path)
result = process_document(doc)  # if this throws, doc is never closed
doc.close()
return result
```

This prevents file handle leaks which can cause "too many open files" errors in long-running processes.

## File Upload Handling

### 1. Always validate file size on disk after saving

`UploadFile.size` can be `None` with chunked uploads, so always check the actual file size on disk after writing to a temp file:

```python
# BAD - file.size can be None, bypassing the check
if file.size and file.size > MAX_UPLOAD_SIZE:
    raise HTTPException(status_code=413, detail="File too large")

# GOOD - check actual size on disk after saving
shutil.copyfileobj(file.file, tmp)
actual_size = tmp_path.stat().st_size
if actual_size > MAX_UPLOAD_SIZE:
    raise HTTPException(status_code=413, detail="File too large")
```

### 2. Always preserve and store the original filename

When processing uploads through temp files, never store the temp path in the database. Pass the original filename through the processing pipeline:

```python
# BAD - stores "/var/folders/.../tmp7l6xen1j.pdf" in the database
db.insert_document(file_path=str(tmp_path), ...)

# GOOD - stores the user's original filename
db.insert_document(file_path=original_filename or str(tmp_path), ...)
```

## Multi-Table Operations

### Use database transactions for atomic multi-table inserts

When inserting records across multiple tables (e.g., document + chunks), use a single database transaction so both operations succeed or fail together:

```python
def insert_document_with_chunks(self, file_hash, file_path, chunks, metadata=None):
    """Insert document and chunks atomically in a single transaction."""
    try:
        with self.conn.cursor() as cur:
            # Insert document
            cur.execute("INSERT INTO documents (...) VALUES (...) RETURNING *", ...)
            doc = cur.fetchone()

            # Insert chunks with the document_id
            if chunks:
                execute_values(cur, "INSERT INTO chunks (...) VALUES %s", ...)

        # Commit both operations together
        self.conn.commit()
        return doc, chunks
    except Exception:
        self.conn.rollback()
        raise
```

This ensures atomic operations - if chunk insertion fails, the document insertion is also rolled back automatically.

## Batch Operation Patterns

### Track failures in batch results

When processing batches, include failed items in results with error information rather than silently skipping them:

```python
class BatchResult(BaseModel):
    item: Item | None = None
    error: str | None = None

def process_batch(items: list[Item]) -> list[BatchResult]:
    results = []
    for item in items:
        try:
            processed = process_item(item)
            results.append(BatchResult(item=processed))
        except Exception as e:
            logger.error("failed to process item", item_id=item.id, error=str(e))
            results.append(BatchResult(error=str(e)))
    return results
```

This allows callers to:
1. Know exactly which items failed and why
2. Retry only failed items
3. Generate accurate success/failure reports

### Sequential vs Parallel Batch Processing

For I/O-bound operations like PDF ingestion, parallel processing can improve throughput. Here's the pattern:

**Sequential (simpler, use for debugging or when order matters):**

```python
def ingest_batch(self, file_paths: list[Path]) -> list[IngestResult]:
    results = []
    for file_path in file_paths:
        try:
            result = self.ingest(file_path)
            results.append(result)
        except Exception as e:
            results.append(IngestResult(error=str(e)))
    return results
```

**Parallel (with ThreadPoolExecutor for I/O-bound tasks):**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def ingest_batch(self, file_paths: list[Path], max_workers: int = 4) -> list[IngestResult]:
    results_dict: dict[int, IngestResult] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(self._ingest_worker, fp): i
            for i, fp in enumerate(file_paths)
        }

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results_dict[idx] = future.result()
            except Exception as e:
                results_dict[idx] = IngestResult(error=str(e))

    # Preserve input order
    return [results_dict[i] for i in range(len(file_paths))]
```

**Important:** When using parallel processing with database connections:
- psycopg2 connections are NOT thread-safe
- Each worker thread must create its own connection
- Store the connection string (not the connection) in the class

## Testing Patterns

### 1. Use explicit table truncation for test isolation

Always truncate tables between tests to ensure test isolation. Use an `autouse` fixture that runs before each test:

```python
@pytest.fixture(autouse=True)
def truncate_tables(db):
    """Truncate tables before each test for isolation."""
    db.truncate_tables()
    yield
```

This prevents test interdependencies and ensures each test starts with a clean database state.

### 2. Pass migrations directory explicitly in tests

```python
MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"

@pytest.fixture(scope="module")
def db():
    store = PgVectorStore(connection_string)
    store.connect()
    store.run_migrations(MIGRATIONS_DIR)  # Always pass explicitly
    yield store
    store.disconnect()
```

## Structured Logging

Use the structured JSON logger for all log output. This matches the Go slog format for consistency across services.

### Output Format

```json
{"time":"2026-02-03T14:06:20.829529-05:00","level":"INFO","source":{"function":"connect","file":"database.py","line":25},"msg":"connected to database","duration_ms":12.34}
```

### Basic Usage

```python
from pdf_llm_server.logger import logger

# Simple message
logger.info("connected to database")

# With additional fields
logger.info("document inserted", document_id="abc-123", duration_ms=45.2)

# Error logging
logger.error("operation failed", error=str(e), document_id="abc-123")
```

### Context Fields

Use `set_context` / `clear_context` to attach request-scoped data that should appear in **all** log entries for the duration of an operation. This avoids passing identifiers manually to every `logger` call.

**When to use:** Any function that represents a top-level unit of work — an HTTP request handler, a background task worker, or a batch-processing entry point (e.g., `ingest_document`). Set context at the start of the function and clear it in a `finally` block so it is always cleaned up, even on exceptions.

**When NOT to use:** Helper functions called within an already-contextualized scope. Only the outermost entry point should set and clear context.

```python
from pdf_llm_server.logger import set_context, clear_context, logger

# In an HTTP request handler
set_context(request_id="req-123", user_id="user-456")

# In a batch-processing entry point
def ingest_document(file_path, file_name):
    set_context(file_name=file_name)
    try:
        # All logs inside this block automatically include file_name
        logger.info("processing started")
        process(file_path)
        logger.info("processing complete")
    finally:
        clear_context()
```

### Logging Guidelines

1. **Always include `duration_ms`** for operations that have measurable latency (DB queries, API calls)
2. **Include identifiers** like `document_id`, `chunk_id` for traceability
3. **Log at appropriate levels**: `info` for normal operations, `error` for failures, `debug` for verbose output
4. **Use structured fields** instead of string interpolation for queryable logs

## Module & Import Hygiene

### 1. No lazy imports inside functions

All imports belong at the top of the module. Do not hide imports inside functions to defer loading:

```python
# BAD - import hidden inside function
def parse_pdf_reducto(file_path):
    from reducto import Reducto
    client = Reducto(api_key=api_key)
    ...

# GOOD - import at module level
from reducto.reducto import Reducto

class ReductoParser:
    def __init__(self, api_key):
        self.client = Reducto(api_key=api_key)
```

If a dependency is optional, guard it at the module level with a try/except and a clear error at construction time — not by hiding the import.

### 2. No circular imports — extract shared models

When two modules need each other's symbols, extract the shared types into a separate module:

```
# BAD - circular: pdf_parser.py imports reducto_parser, reducto_parser imports pdf_parser
pdf_parser.py  <-->  reducto_parser.py

# GOOD - both import from a shared models module
parser_models.py  <--  pdf_parser.py
                  <--  reducto_parser.py
```

Shared Pydantic models and data classes should live in their own file (e.g., `parser_models.py`) so any module can import them without creating cycles.

### 3. External clients should be classes, not per-call setup

When integrating with external services (APIs, SDKs), wrap the client in a class that initializes once. Do not re-read env vars and re-create clients on every function call:

```python
# BAD - reads env var and creates client every call
def parse(file_path):
    api_key = os.getenv("REDUCTO_API_KEY")
    client = Reducto(api_key=api_key)
    return client.parse(file_path)

# GOOD - class initializes once, reuses client
class ReductoParser:
    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.getenv("REDUCTO_API_KEY")
        if not api_key:
            raise ValueError("REDUCTO_API_KEY is not set")
        self.client = Reducto(api_key=api_key)

    def parse(self, file_path):
        return self.client.parse(file_path)
```

### 4. Keep implementation details inside the responsible module

Callers should not need to know internal details of a dependency. If module A dispatches to module B, don't duplicate B's internal logic in the caller:

```python
# BAD - caller knows that reducto doesn't need OCR
parser = os.getenv("PDF_PARSER", "pymupdf")
if parser == "reducto":
    needs_ocr = False
else:
    needs_ocr = assess_needs_ocr(file_path)
parsed_doc = parse_pdf(file_path)

# GOOD - parse_pdf owns the OCR decision internally
parsed_doc = parse_pdf(file_path)  # handles OCR assessment for pymupdf, skips for reducto
```

## Deprecating / Removing Endpoints

When removing an API endpoint, always do it in this order across separate PRs:

1. **Frontend first** — Remove all client-side calls to the endpoint
2. **Backend endpoint** — Remove the route handler
3. **Data models** — Remove request/response models (if no longer referenced)

This ensures no client is calling an endpoint before it's removed, and no models are deleted while still in use.

## Frontend Code Organization

### Directory structure

```
frontend/src/
├── components/       # React components with barrel export (index.ts)
├── hooks/            # Custom hooks with barrel export (index.ts)
├── lib/              # Types and API client (NO barrel export)
│   ├── types.ts      # All shared TypeScript interfaces
│   └── api.ts        # Typed fetch wrappers for backend API
├── routes/           # TanStack Router file-based routes
└── styles/           # Global styles (TailwindCSS)
```

### Conventions

- Create barrel exports (`index.ts`) for `components/` and `hooks/` directories
- Keep all shared types in `lib/types.ts` — do NOT create a separate `types/` directory
- Do NOT create barrel exports for `lib/`
- API wrappers go in `lib/api.ts`

## Code Review (Mesa)

[Mesa](https://mesa.dev) is an AI-powered code review platform that runs automated review agents on pull requests. It provides senior-level reviews with full codebase context and customizable standards.

The `mesa.config.ts` file at the repo root configures which review agents run, what files they cover, and what rules they enforce. Each agent has:

- **`name`** — label for the reviewer (e.g. `backend`, `frontend`, `security`, `database`)
- **`model`** — reasoning tier (`high-reasoning` or `fast`)
- **`context`** — how much of the codebase the agent can see (`full-codebase`)
- **`fileMatch`** — glob patterns for which files trigger this agent
- **`rules`** — project-specific rules the agent enforces during review

Reviews are triggered on `pull_request` events. When updating project conventions in CLAUDE.md, also update the corresponding rules in `mesa.config.ts` to keep automated reviews in sync.
