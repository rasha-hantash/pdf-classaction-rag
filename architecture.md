                                                                                
  - 4 copy/paste agent prompts - each self-contained with project path, branch   
  name, tasks, and verification command                                          
  - 3-phase execution flow - Agent 1 → Agents 2 & 3 (parallel) → Agent 4         
  - File ownership table - prevents conflicts between agents                     
  - Step-by-step Conductor instructions - manual workflow through the UI         
  - Merge order guidance - critical for dependency resolution                    
                                                                                 
  One note: Agents 1 and 3 both modify pyproject.toml (adding different          
  dependencies), so you'll need to resolve that manually when merging Agent 3's  
  branch.                                                                        
  ⎿  User rejected Claude's plan:                                                
     ╭──────────────────────────────────────────────────────────────────────────╮
     │ Plan: RAG Pipeline with Conductor.build Multi-Agent Orchestration        │
     │                                                                          │
     │ Overview                                                                 │
     │                                                                          │
     │ Use https://www.conductor.build/ to orchestrate 4 Claude Code agents     │
     │ building a RAG pipeline in parallel. Each agent works in an isolated Git │
     │ worktree, avoiding conflicts.                                            │
     │                                                                          │
     │ What is Conductor.build?                                                 │
     │                                                                          │
     │ Conductor by Melty Labs runs multiple Claude Code agents on your Mac:    │
     │ - Each agent gets its own isolated Git worktree                          │
     │ - Dashboard shows all agents' progress                                   │
     │ - Uses your existing Claude Code auth (API key or Pro/Max plan)          │
     │ - Install from: https://www.conductor.build/                             │
     │                                                                          │
     │ Agent Architecture                                                       │
     │                                                                          │
     │ Phase 1 (Sequential):                                                    │
     │ ┌─────────────────────────────────────────────────────────────────┐      │
     │ │  AGENT 1: Data Model & Infrastructure                           │      │
     │ │  Branch: rag/data-model                                         │      │
     │ │  Creates: docker-compose, migrations, rag/models.py, database.py│      │
     │ └─────────────────────────────────────────────────────────────────┘      │
     │                               ▼                                          │
     │ Phase 2 (Parallel - both run simultaneously):                            │
     │ ┌─────────────────────────────┐  ┌────────────────────────────────┐      │
     │ │  AGENT 2: PDF Ingestion     │  │  AGENT 3: Embeddings           │      │
     │ │  Branch: rag/ingestion      │  │  Branch: rag/embeddings        │      │
     │ │  Creates: chunking.py,      │  │  Creates: embeddings.py        │      │
     │ │  ocr.py, ingestion.py       │  │  (OpenAI text-embedding-3)     │      │
     │ └─────────────────────────────┘  └────────────────────────────────┘      │
     │                               ▼                                          │
     │ Phase 3 (Sequential):                                                    │
     │ ┌─────────────────────────────────────────────────────────────────┐      │
     │ │  AGENT 4: Retrieval & API                                       │      │
     │ │  Branch: rag/retrieval                                          │      │
     │ │  Creates: retriever.py, new API endpoints in server.py          │      │
     │ └─────────────────────────────────────────────────────────────────┘      │
     │                                                                          │
     │ File Ownership (Prevents Conflicts)                                      │
     │                                                                          │
     │ ┌─────────────────────┬─────────┬─────────┬─────────┬─────────┐          │
     │ │        File         │ Agent 1 │ Agent 2 │ Agent 3 │ Agent 4 │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ docker-compose.yaml │ CREATE  │    -    │    -    │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ migrations/*.sql    │ CREATE  │    -    │    -    │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ rag/models.py       │ CREATE  │    -    │    -    │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ rag/database.py     │ CREATE  │    -    │    -    │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ rag/chunking.py     │    -    │ CREATE  │    -    │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ rag/ocr.py          │    -    │ CREATE  │    -    │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ rag/ingestion.py    │    -    │ CREATE  │    -    │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ rag/embeddings.py   │    -    │    -    │ CREATE  │    -    │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ rag/retriever.py    │    -    │    -    │    -    │ CREATE  │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ server.py           │    -    │    -    │    -    │ MODIFY  │          │
     │ ├─────────────────────┼─────────┼─────────┼─────────┼─────────┤          │
     │ │ pyproject.toml      │ MODIFY  │    -    │ MODIFY  │    -    │          │
     │ └─────────────────────┴─────────┴─────────┴─────────┴─────────┘          │
     │ ---                                                                      │
     │ Agent Prompts for Conductor.build                                        │
     │                                                                          │
     │ AGENT 1: Data Model & Infrastructure                                     │
     │                                                                          │
     │ Branch: rag/data-model                                                   │
     │                                                                          │
     │ You are implementing the database foundation for a RAG pipeline.         │
     │                                                                          │
     │ PROJECT: /Users/rashasaadeh/workspace/personal/python-practice-interviews│
     │ /modus/practice-pdf-llm/                                                 │
     │ REFERENCE: docs/rag-pipeline-architecture.md                             │
     │                                                                          │
     │ TASKS:                                                                   │
     │ 1. Create docker-compose.yaml with PostgreSQL 16 + pgvector              │
     │    - Port: 5432, Database: pdf_llm_rag                                   │
     │                                                                          │
     │ 2. Create migrations/:                                                   │
     │    - 001_create_documents_table.up.sql / .down.sql                       │
     │    - 002_create_chunks_table.up.sql / .down.sql                          │
     │    Tables: documents (id, tenant_id, file_hash, file_path, metadata      │
     │ JSONB, created_at)                                                       │
     │            chunks (id, document_id FK, content, chunk_type, page_number, │
     │ position, embedding vector(1536), created_at)                            │
     │                                                                          │
     │ 3. Create src/pdf_llm_server/rag/models.py:                              │
     │    - IngestedDocument, ChunkRecord, SearchResult (Pydantic)              │
     │                                                                          │
     │ 4. Create src/pdf_llm_server/rag/database.py:                            │
     │    - PgVectorStore class (psycopg2)                                      │
     │    - Methods: insert_document(), insert_chunks(), similarity_search()    │
     │                                                                          │
     │ 5. Create src/pdf_llm_server/rag/__init__.py                             │
     │                                                                          │
     │ 6. Update pyproject.toml: add psycopg2-binary>=2.9.0, pgvector>=0.2.0    │
     │                                                                          │
     │ 7. Create tests/test_rag_database.py                                     │
     │                                                                          │
     │ VERIFY: docker compose up -d && pytest tests/test_rag_database.py        │
     │                                                                          │
     │ ---                                                                      │
     │ AGENT 2: PDF Ingestion Pipeline                                          │
     │                                                                          │
     │ Branch: rag/ingestion (base: main after Agent 1 merged)                  │
     │                                                                          │
     │ You are implementing PDF ingestion and chunking for a RAG system.        │
     │                                                                          │
     │ PROJECT: /Users/rashasaadeh/workspace/personal/python-practice-interviews│
     │ /modus/practice-pdf-llm/                                                 │
     │ REFERENCE: docs/rag-pipeline-architecture.md                             │
     │ EXISTING: pdf_parser.py (PyMuPDF), rag/models.py, rag/database.py (from  │
     │ Agent 1)                                                                 │
     │                                                                          │
     │ TASKS:                                                                   │
     │ 1. Create src/pdf_llm_server/rag/chunking.py:                            │
     │    - fixed_size_chunking(text, chunk_size=1000, overlap=200)             │
     │    - semantic_chunking_by_paragraphs(text, max_chunk_size=1500)          │
     │    - detect_content_type(text) -> heading/paragraph/list/table           │
     │                                                                          │
     │ 2. Create src/pdf_llm_server/rag/ocr.py:                                 │
     │    - assess_needs_ocr(file_path) -> bool                                 │
     │    - ocr_pdf_with_tesseract(file_path, dpi=300) (optional dependency)    │
     │                                                                          │
     │ 3. Create src/pdf_llm_server/rag/ingestion.py:                           │
     │    - ingest_document(file_path, tenant_id, metadata)                     │
     │    - RAGIngestionPipeline class                                          │
     │    - Reuse existing pdf_parser.parse_pdf()                               │
     │                                                                          │
     │ 4. Create tests/test_rag_ingestion.py                                    │
     │                                                                          │
     │ DO NOT modify: database.py, models.py (owned by Agent 1)                 │
     │                                                                          │
     │ VERIFY: pytest tests/test_rag_ingestion.py                               │
     │                                                                          │
     │ ---                                                                      │
     │ AGENT 3: Embedding Generation                                            │
     │                                                                          │
     │ Branch: rag/embeddings (base: main after Agent 1 merged)                 │
     │                                                                          │
     │ You are implementing embedding generation for a RAG system.              │
     │                                                                          │
     │ PROJECT: /Users/rashasaadeh/workspace/personal/python-practice-interviews│
     │ /modus/practice-pdf-llm/                                                 │
     │ REFERENCE: docs/rag-pipeline-architecture.md                             │
     │ DIMENSION: 1536 (matches pgvector schema)                                │
     │                                                                          │
     │ TASKS:                                                                   │
     │ 1. Create src/pdf_llm_server/rag/embeddings.py:                          │
     │    - EmbeddingClient class                                               │
     │    - generate_embeddings(texts: List[str]) -> List[List[float]]          │
     │    - Use OpenAI text-embedding-3-small (OPENAI_API_KEY env var)          │
     │    - Batch processing (max 2048 per request)                             │
     │    - Optional: simple content-hash cache                                 │
     │                                                                          │
     │ 2. Update pyproject.toml: add openai>=1.0.0                              │
     │                                                                          │
     │ 3. Create tests/test_rag_embeddings.py (mock OpenAI API)                 │
     │                                                                          │
     │ DO NOT modify any files from Agent 1 or Agent 2                          │
     │                                                                          │
     │ VERIFY: pytest tests/test_rag_embeddings.py                              │
     │                                                                          │
     │ ---                                                                      │
     │ AGENT 4: Retrieval & API Integration                                     │
     │                                                                          │
     │ Branch: rag/retrieval (base: main after Agents 2 & 3 merged)             │
     │                                                                          │
     │ You are implementing retrieval and API endpoints for a RAG system.       │
     │                                                                          │
     │ PROJECT: /Users/rashasaadeh/workspace/personal/python-practice-interviews│
     │ /modus/practice-pdf-llm/                                                 │
     │ REFERENCE: docs/rag-pipeline-architecture.md                             │
     │ EXISTING: server.py, llm_client.py, rag/* (from Agents 1-3)              │
     │                                                                          │
     │ TASKS:                                                                   │
     │ 1. Create src/pdf_llm_server/rag/retriever.py:                           │
     │    - RAGRetriever class                                                  │
     │    - retrieve(query, tenant_id, top_k=5) -> List[SearchResult]           │
     │    - query(question, tenant_id) -> {answer, sources}                     │
     │    - Use Claude for generation (follow llm_client.py pattern)            │
     │                                                                          │
     │ 2. Add RAG endpoints to server.py:                                       │
     │    - POST /rag/ingest: {file_paths, tenant_id, metadata?}                │
     │    - POST /rag/query: {question, tenant_id, top_k?}                      │
     │    - GET /rag/documents/{tenant_id}                                      │
     │                                                                          │
     │ 3. Update rag/__init__.py with all exports                               │
     │                                                                          │
     │ 4. Create tests/test_rag_api.py                                          │
     │                                                                          │
     │ VERIFY: pytest tests/test_rag_api.py && python -c "from                  │
     │ pdf_llm_server.server import app"                                        │
     │                                                                          │
     │ ---                                                                      │
     │ Execution Steps in Conductor.build                                       │
     │                                                                          │
     │ Step 1: Launch Agent 1                                                   │
     │                                                                          │
     │ 1. Open Conductor.build                                                  │
     │ 2. Create new agent with prompt from "AGENT 1" above                     │
     │ 3. Set branch to rag/data-model                                          │
     │ 4. Wait for completion                                                   │
     │ 5. Review and merge to main                                              │
     │                                                                          │
     │ Step 2: Launch Agents 2 & 3 (Parallel)                                   │
     │                                                                          │
     │ 1. In Conductor, create two agents simultaneously:                       │
     │   - Agent 2 with "AGENT 2" prompt, branch rag/ingestion                  │
     │   - Agent 3 with "AGENT 3" prompt, branch rag/embeddings                 │
     │ 2. Both work in parallel (isolated worktrees)                            │
     │ 3. Wait for both to complete                                             │
     │ 4. Review and merge both to main                                         │
     │                                                                          │
     │ Step 3: Launch Agent 4                                                   │
     │                                                                          │
     │ 1. Create agent with "AGENT 4" prompt, branch rag/retrieval              │
     │ 2. Wait for completion                                                   │
     │ 3. Review and merge to main                                              │
     │                                                                          │
     │ Step 4: Final Verification                                               │
     │                                                                          │
     │ docker compose up -d                                                     │
     │ pytest                                                                   │
     │ python -m pdf_llm_server.server                                          │
     │ # Test endpoints at http://localhost:8000/docs                           │
     │                                                                          │
     │ ---                                                                      │
     │ Final File Structure                                                     │
     │                                                                          │
     │ practice-pdf-llm/                                                        │
     │ ├── docker-compose.yaml              # Agent 1                           │
     │ ├── migrations/                                                          │
     │ │   ├── 001_create_documents_table.up.sql                                │
     │ │   ├── 001_create_documents_table.down.sql                              │
     │ │   ├── 002_create_chunks_table.up.sql                                   │
     │ │   └── 002_create_chunks_table.down.sql                                 │
     │ ├── src/pdf_llm_server/                                                  │
     │ │   ├── server.py                    # Modified by Agent 4               │
     │ │   └── rag/                                                             │
     │ │       ├── __init__.py              # Agent 1 + Agent 4                 │
     │ │       ├── models.py                # Agent 1                           │
     │ │       ├── database.py              # Agent 1                           │
     │ │       ├── chunking.py              # Agent 2                           │
     │ │       ├── ocr.py                   # Agent 2                           │
     │ │       ├── ingestion.py             # Agent 2                           │
     │ │       ├── embeddings.py            # Agent 3                           │
     │ │       └── retriever.py             # Agent 4                           │
     │ └── tests/                                                               │
     │     ├── test_rag_database.py         # Agent 1                           │
     │     ├── test_rag_ingestion.py        # Agent 2                           │
     │     ├── test_rag_embeddings.py       # Agent 3                           │
     │     └── test_rag_api.py              # Agent 4                           │
     │                                                                          │
     │ ---                                                                      │
     │ Environment Variables Required                                           │
     │                                                                          │
     │ # For Agent 3 embeddings                                                 │
     │ OPENAI_API_KEY=sk-...                                                    │
     │                                                                          │
     │ # For database (Agent 1 sets default in docker-compose)                  │
     │ DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pdf_llm_rag   │
     │                                                                          │
     │ # Existing (for Claude LLM)                                              │
     │ ANTHROPIC_API_KEY=sk-ant-...                                             │
     │                                                                          │
     │ ---                                                                      │
     │ Notes                                                                    │
     │                                                                          │
     │ - Conductor.build handles Git worktrees - each agent works in isolation  │
     │ - Merge order matters: Agent 1 first, then 2 & 3, then 4                 │
     │ - pyproject.toml conflict: Agent 1 and Agent 3 both modify it; resolve   │
     │ manually if needed                                                       │
     │ - Reference doc: All agents should read docs/rag-pipeline-architecture.md│
     │  for implementation details                                              │
     │                                                                          │
     ╰──────────────────────────────────────────────────────────────────────────╯
                                       
