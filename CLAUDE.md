# Project Conventions

## Database Migrations

Always use [golang-migrate/migrate](https://github.com/golang-migrate/migrate) to create new migrations:

```bash
migrate create -ext sql -dir migrations -seq <migration_name>
```

This creates properly formatted migration files with sequential numbering.

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

Use context fields for request-scoped data that should appear in all logs:

```python
from pdf_llm_server.logger import set_context, clear_context

# Set context at request start
set_context(request_id="req-123", user_id="user-456")

# All subsequent logs include these fields
logger.info("processing started")  # includes request_id and user_id

# Clear at request end
clear_context()
```

### Logging Guidelines

1. **Always include `duration_ms`** for operations that have measurable latency (DB queries, API calls)
2. **Include identifiers** like `document_id`, `chunk_id` for traceability
3. **Log at appropriate levels**: `info` for normal operations, `error` for failures, `debug` for verbose output
4. **Use structured fields** instead of string interpolation for queryable logs
