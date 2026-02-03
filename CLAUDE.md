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
