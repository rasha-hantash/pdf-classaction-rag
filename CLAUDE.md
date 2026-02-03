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
