"""RAG retriever for similarity search and response generation."""

import os
import time

from anthropic import Anthropic
from pydantic import BaseModel

from ..logger import logger
from .database import PgVectorStore
from .embeddings import EmbeddingClient
from .models import SearchResult


class SourceReference(BaseModel):
    """A source reference from a retrieved chunk."""

    file_path: str
    page_number: int | None
    content_preview: str  # First 200 chars of chunk


class RAGResponse(BaseModel):
    """Response from a RAG query."""

    answer: str
    sources: list[SourceReference]
    chunks_used: int


class RAGRetriever:
    """Retriever for RAG queries with similarity search and Claude generation."""

    DEFAULT_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

Rules:
1. Only use information from the provided context to answer the question
2. If the context doesn't contain enough information to answer, say so clearly
3. Cite specific sources when possible (e.g., "According to page X...")
4. Be concise and direct in your answers
5. If the question is ambiguous, ask for clarification"""

    def __init__(
        self,
        db: PgVectorStore,
        embedding_client: EmbeddingClient,
        anthropic_api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: str | None = None,
    ):
        """Initialize the RAG retriever.

        Args:
            db: PgVectorStore database connection.
            embedding_client: EmbeddingClient for generating query embeddings.
            anthropic_api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
            model: Claude model to use for generation.
            system_prompt: Custom system prompt for Claude. Uses default if not provided.
        """
        self.db = db
        self.embedding_client = embedding_client
        self.model = model
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key required: provide anthropic_api_key or set ANTHROPIC_API_KEY"
            )
        self._anthropic = Anthropic(api_key=api_key)

    def retrieve(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Retrieve relevant chunks for a query.

        Args:
            query: The search query.
            top_k: Number of top results to return.

        Returns:
            List of SearchResult objects sorted by relevance.
        """
        start = time.perf_counter()

        # Generate query embedding
        query_embedding = self.embedding_client.generate_embedding(query)

        # Search for similar chunks
        results = self.db.similarity_search(query_embedding, top_k=top_k)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "retrieval completed",
            query_length=len(query),
            top_k=top_k,
            results_count=len(results),
            duration_ms=round(duration_ms, 2),
        )

        return results

    def _build_context(self, results: list[SearchResult]) -> str:
        """Build context string from search results.

        Args:
            results: List of SearchResult objects.

        Returns:
            Formatted context string for the LLM.
        """
        if not results:
            return "No relevant context found."

        context_parts = []
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            doc = result.document

            # Build source info
            source_info = []
            if doc:
                source_info.append(f"Source: {doc.file_path}")
            if chunk.page_number is not None:
                source_info.append(f"Page: {chunk.page_number}")
            if chunk.chunk_type:
                source_info.append(f"Type: {chunk.chunk_type}")

            header = f"[Context {i}] " + " | ".join(source_info) if source_info else f"[Context {i}]"

            context_parts.append(f"{header}\n{chunk.content}")

        return "\n\n---\n\n".join(context_parts)

    def _build_sources(self, results: list[SearchResult]) -> list[SourceReference]:
        """Build source references from search results.

        Args:
            results: List of SearchResult objects.

        Returns:
            List of SourceReference objects.
        """
        sources = []
        for result in results:
            chunk = result.chunk
            doc = result.document

            sources.append(
                SourceReference(
                    file_path=doc.file_path if doc else "unknown",
                    page_number=chunk.page_number,
                    content_preview=chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                )
            )

        return sources

    def query(self, question: str, top_k: int = 5) -> RAGResponse:
        """Answer a question using RAG.

        Retrieves relevant chunks, builds context, and generates a response
        using Claude.

        Args:
            question: The question to answer.
            top_k: Number of chunks to retrieve for context.

        Returns:
            RAGResponse with answer and source references.
        """
        start = time.perf_counter()

        # Retrieve relevant chunks
        results = self.retrieve(question, top_k=top_k)

        if not results:
            return RAGResponse(
                answer="I couldn't find any relevant information in the documents to answer your question.",
                sources=[],
                chunks_used=0,
            )

        # Build context from results
        context = self._build_context(results)

        # Generate response with Claude
        user_message = f"""Context:
{context}

Question: {question}

Please answer the question based only on the provided context."""

        generation_start = time.perf_counter()
        response = self._anthropic.messages.create(
            model=self.model,
            max_tokens=2048,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        generation_duration_ms = (time.perf_counter() - generation_start) * 1000

        if not response.content:
            raise ValueError("Empty response from Claude API")
        answer = response.content[0].text

        # Build source references
        sources = self._build_sources(results)

        total_duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "rag query completed",
            question_length=len(question),
            chunks_used=len(results),
            answer_length=len(answer),
            generation_duration_ms=round(generation_duration_ms, 2),
            total_duration_ms=round(total_duration_ms, 2),
        )

        return RAGResponse(
            answer=answer,
            sources=sources,
            chunks_used=len(results),
        )
