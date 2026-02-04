# PDF RAG Pipeline

A document ingestion and retrieval-augmented generation (RAG) system for PDF processing.

## Requirements

- Python 3.14+
- Docker (for PostgreSQL + pgvector)
- OpenAI API key (for embeddings)
- Anthropic API key (for RAG responses)

## Setup

### 1. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL 16 with pgvector on port 5432.

### 2. Install dependencies

```bash
uv sync
```

### 3. Set environment variables

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pdf_llm_rag
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

## Running the Server

```bash
uv run python main.py
```

The server runs at http://localhost:8000. API docs available at http://localhost:8000/docs.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check (DB connectivity) |
| POST | `/api/v1/rag/ingest` | Upload and ingest a PDF file |
| POST | `/api/v1/rag/query` | Ask a question using RAG |

## Usage Examples

### Ingest a PDF

```bash
curl -X POST http://localhost:8000/api/v1/rag/ingest \
  -F "file=@document.pdf"
```


### Query the documents

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?", "top_k": 5}'
```


## Running Tests

```bash
uv run pytest tests/ -v
```

Tests require the database to be running. The test suite uses table truncation for isolation between tests.

## Project Structure

```
conakry/
├── main.py                      # Server entry point
├── docker-compose.yaml          # PostgreSQL + pgvector
├── migrations/                  # Database migrations
├── src/pdf_llm_server/
│   ├── server.py               # FastAPI REST API
│   ├── logger.py               # Structured JSON logging
│   └── rag/
│       ├── database.py         # PgVectorStore
│       ├── embeddings.py       # OpenAI embeddings
│       ├── ingestion.py        # PDF ingestion pipeline
│       ├── retriever.py        # RAG query with Claude
│       ├── pdf_parser.py       # PyMuPDF parsing
│       ├── chunking.py         # Text chunking strategies
│       └── ocr.py              # OCR detection
└── tests/
```


 ---                                                                                                                                                                                                        
  What I Built: PDF RAG Pipeline                                                                                                                                                                           
                                                                                                                                                                                                             
  A retrieval-augmented generation system for querying legal documents (Facebook privacy settlement PDFs).                                                                                                 

  The Pipeline

  1. Ingestion
  - Parse PDFs using PyMuPDF (fitz) → extracts text blocks, tables, page numbers
  - Chunk the content (more on this below)
  - Generate embeddings via OpenAI text-embedding-3-small (1536 dimensions)
  - Store in PostgreSQL with pgvector extension

  2. Retrieval
  - User asks a question → generate embedding for the query
  - Cosine similarity search against stored chunks (using pgvector's <=> operator)
  - Return top-k most relevant chunks

  3. Generation
  - Build context from retrieved chunks (includes source file, page number)
  - Send to Claude with a system prompt that says "only use the provided context"
  - Return answer + source references

  Chunking Strategy

  I have two options:
  - Semantic chunking: Splits by paragraph boundaries (double newlines), merges small paragraphs together up to ~1500 chars. Falls back to fixed-size if a single paragraph is huge.
  - Fixed-size chunking: 1000 chars with 200 char overlap, tries to break at word boundaries.

  I went with semantic as the default because legal docs have natural paragraph structure, and keeping paragraphs intact preserves meaning better than arbitrary cuts.

  A Few Things I'd Improve

  - Hybrid search: Add BM25/keyword search alongside vector search. Legal docs have specific terms (case numbers, dates) that exact match would catch better.
  - Chunk size tuning: 1500 chars was a guess. Would want to experiment based on retrieval quality.
  - Reranking: After initial retrieval, could use a cross-encoder to rerank results before sending to the LLM.
  - OCR: I detect if a PDF might need OCR (scanned docs) but don't actually run it yet.
  - Batch uploads: Allow the user to upload all their PDF files in a batch
  - Figure out teh following bug: The issue is embedded fonts with corrupted encoding on pages 52-56. PyMuPDF is extracting binary garbage instead of readable text because these pages use fonts with broken or non-standard character mappings. - Feldman Appeal 0021 Appellants Opening Brief 050424.pdf - Contains NUL (0x00) characters in the
  text that PostgreSQL cannot store

  Tech Stack

  - Python, FastAPI
  - PostgreSQL + pgvector
  - OpenAI embeddings, Claude for generation
  - PyMuPDF for PDF parsing
