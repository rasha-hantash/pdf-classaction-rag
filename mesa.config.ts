export default {
  review: {
    agents: [
      {
        name: "backend",
        model: "high-reasoning",
        context: "full-codebase",
        fileMatch: [
          "backend/src/**/*.py",
          "backend/tests/**/*.py",
          "backend/scripts/**/*.py",
          "backend/main.py",
        ],
        rules: [
          // CLI input validation
          "Validate numeric CLI arguments beyond argparse type checks — reject zero and negative values with parser.error()",
          "Use 'is not None' for optional numeric arguments — never use truthiness (0 is falsy, gets silently skipped)",

          // psycopg2 transaction safety
          "Every method calling conn.commit() must have a matching conn.rollback() in an except block",
          "Use execute_values() for batch inserts — never insert rows in a loop",
          "Import psycopg2 extras explicitly: from psycopg2.extras import Json, RealDictCursor, execute_values",
          "Use RealDictCursor for all data-returning queries",

          // Resource cleanup
          "fitz.open(), open(), and external resource handles must use try-finally to guarantee cleanup",
          "File size validation must use Path.stat().st_size on disk — never trust UploadFile.size",
          "Preserve original filenames when storing in the database — never store temp file paths",

          // Atomic operations
          "Multi-table inserts (e.g. document + chunks) must be atomic in a single transaction",
          "Batch results must track failures with error information — never silently skip failed items",

          // Structured logging
          "Use the structured JSON logger (from pdf_llm_server.logger import logger) — no print() or stdlib logging",
          "Include duration_ms for operations with measurable latency (DB queries, API calls, parsing)",
          "Include identifiers (document_id, chunk_id) in log entries for traceability",

          // Module & import hygiene
          "All imports at module level — no lazy imports inside functions",
          "No circular imports — extract shared models into a separate module",
          "External API clients must be classes that initialize once, not per-call setup",
          "Callers must not duplicate internal logic of their dependencies",

          // Testing patterns
          "Tests must use autouse truncation fixtures for table isolation",
          "Pass migrations directory explicitly in test fixtures",

          // Memory leak detection
          "Flag reference cycles and self-referencing assignments",
          "Flag gc.disable() or gc.set_threshold() without clear justification",
          "Flag unbounded caches without eviction — suggest lru_cache, WeakValueDictionary, or TTL",
          "Flag file handles or DB connections not closed in exception paths",
          "Prefer generators over materializing large lists for PDF processing pipelines",
          "Flag shared psycopg2 connections across ThreadPoolExecutor workers — each thread needs its own connection",
          "Flag loading entire PDFs into memory without streaming or chunking",
          "Flag event listeners registered without corresponding cleanup",
        ],
      },
      {
        name: "frontend",
        model: "fast",
        context: "full-codebase",
        fileMatch: [
          "frontend/src/**/*.ts",
          "frontend/src/**/*.tsx",
          "frontend/src/**/*.css",
        ],
        rules: [
          // Code organization
          "Barrel exports (index.ts) required for components/ and hooks/ directories",
          "All shared TypeScript interfaces must live in lib/types.ts — no separate types/ directory",
          "No barrel export for the lib/ directory",
          "API fetch wrappers must live in lib/api.ts",

          // React best practices
          "Flag missing hook dependencies in useEffect, useCallback, useMemo",
          "No explicit any types — use proper TypeScript types",

          // Cross-boundary consistency
          "Frontend types must stay in sync with backend API response schemas",
          "Endpoint deprecation order: remove frontend calls first, then backend route, then data models",
        ],
      },
      {
        name: "security",
        model: "high-reasoning",
        context: "full-codebase",
        fileMatch: [
          "backend/src/**/*.py",
          "backend/scripts/**/*.py",
          "frontend/src/lib/api.ts",
          "docker-compose.yaml",
          "backend/migrations/**/*.sql",
        ],
        rules: [
          // SQL injection
          "All SQL queries must use parameterized queries — no string interpolation or f-strings in SQL",

          // File handling
          "Validate file paths against path traversal (../ sequences, symlink escapes)",
          "File uploads must validate both type and size on disk after saving",
          "Resolve file paths with .resolve() before read/write operations in functions that accept path arguments",
          "Check file size with path.stat().st_size before reading files into memory — guard against memory exhaustion from large files",

          // HTML generation (applies to any code that builds HTML strings)
          "HTML-escape all user-controlled or external strings interpolated into generated HTML — filenames, PDF text, API responses, database content",
          "Escape </ sequences in JSON embedded in <script> tags to prevent script tag breakout — use json.dumps(...).replace('</','<\\/')",
          "Use DOM APIs (createElement + textContent) instead of innerHTML when building elements from user input in generated JS",
          "Quote and escape all values injected into HTML attributes",

          // Secrets
          "No hardcoded secrets, API keys, or credentials in source code",

          // SSRF / deserialization
          "Validate and restrict URLs before making outbound HTTP requests",
          "No use of pickle, eval(), exec(), or yaml.load() without SafeLoader",

          // Infrastructure
          "Flag CORS wildcard (*) configurations in production settings",
          "Containers must not run as privileged or with unnecessary capabilities",
        ],
      },
      {
        name: "database",
        model: "high-reasoning",
        context: "full-codebase",
        fileMatch: [
          "backend/migrations/**/*.sql",
          "backend/src/pdf_llm_server/rag/database.py",
          "docker-compose.yaml",
          "Taskfile.yml",
        ],
        rules: [
          // Migration conventions
          "Migrations must follow golang-migrate sequential naming: NNNNNN_name.up.sql / NNNNNN_name.down.sql",
          "Every .up.sql migration must have a corresponding .down.sql that fully reverses it",
          "DDL statements should be idempotent (IF NOT EXISTS / IF EXISTS)",

          // psycopg2 patterns
          "conn.commit() must have matching conn.rollback() in except blocks",
          "Use execute_values() for batch inserts — never loop with individual cur.execute()",
          "Use RealDictCursor for all queries returning data",

          // Transaction safety
          "Multi-table inserts must be atomic within a single transaction",
          "No long-running transactions held open across API request boundaries",

          // Schema design
          "Foreign key ON DELETE strategies must be explicitly chosen (CASCADE, SET NULL, RESTRICT)",
          "Vector column dimensions must match the embedding model output size",

          // Connection lifecycle
          "Database connections must be properly closed in disconnect/cleanup methods",
          "psycopg2 connections are not thread-safe — each ThreadPoolExecutor worker needs its own connection",
        ],
      },
      {
        name: "performance",
        model: "high-reasoning",
        context: "full-codebase",
        fileMatch: [
          "backend/src/**/*.py",
          "frontend/src/**/*.ts",
          "frontend/src/**/*.tsx",
        ],
        rules: [
          // Backend: query patterns
          "Flag N+1 queries — querying inside a loop instead of batching with execute_values() or a single JOIN",
          "Flag unbatched inserts — inserting rows one-by-one instead of using execute_values()",
          "Flag SELECT without LIMIT on tables that can grow (documents, chunks, embeddings)",
          "Flag waterfall await calls to independent services — use asyncio.gather() for parallel requests",

          // Backend: resource management
          "Flag DB connections or file handles held open across network I/O or external API calls",
          "Flag blocking synchronous I/O in async handlers without run_in_executor",
          "Flag shared psycopg2 connections across ThreadPoolExecutor workers",

          // Backend: algorithmic
          "Flag O(n^2) patterns — nested loops over growing collections, repeated 'in' checks on lists instead of sets",
          "Flag unbounded caches without eviction — suggest lru_cache, WeakValueDictionary, or TTL",
          "Flag loading entire PDFs into memory without streaming or chunking",

          // Frontend: React rendering
          "Flag inline object/array/function literals in JSX props that cause unnecessary re-renders",
          "Flag missing React.memo on components that receive stable props but re-render due to parent",
          "Flag expensive computations in render body without useMemo",
          "Flag unstable callback references in props without useCallback",

          // Frontend: state management
          "Flag derived state stored in useState — should be a computed variable or useMemo",
          "Flag duplicated state — same data stored in multiple places that can get out of sync",

          // Frontend: loading
          "Flag large components/routes imported eagerly that should use React.lazy() and code splitting",
          "Flag rendering large lists (>100 items) without virtualization/windowing",
          "Flag missing abort controllers on fetch calls in useEffect",
        ],
      },
    ],
    triggers: ["pull_request"],
  },
};
