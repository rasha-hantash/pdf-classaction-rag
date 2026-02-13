"""Re-ranking implementations for RAG retrieval results."""

import os
import time
from abc import ABC, abstractmethod

import cohere
from sentence_transformers import CrossEncoder

from ..logger import logger
from .models import SearchResult


class Reranker(ABC):
    """Abstract base class for re-ranking search results."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Re-rank search results by relevance to the query.

        Args:
            query: The original search query.
            results: List of SearchResult candidates to re-rank.
            top_k: Number of top results to return after re-ranking.

        Returns:
            List of SearchResult objects re-ordered by relevance, truncated to top_k.
        """


class CohereReranker(Reranker):
    """Re-ranks search results using Cohere's rerank API."""

    DEFAULT_MODEL = "rerank-v3.5"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialize the Cohere re-ranker.

        Args:
            api_key: Cohere API key. If not provided, uses COHERE_API_KEY env var.
            model: Cohere rerank model name. Defaults to rerank-v3.5.

        Raises:
            ValueError: If no API key is available.
        """
        api_key = api_key or os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError(
                "Cohere API key required: provide api_key or set COHERE_API_KEY"
            )
        self._client = cohere.ClientV2(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        if not results:
            return []

        start = time.perf_counter()

        documents = [r.chunk.content for r in results]

        response = self._client.rerank(
            model=self._model,
            query=query,
            documents=documents,
            top_n=top_k,
        )

        reranked = []
        for item in response.results:
            original = results[item.index]
            reranked.append(
                SearchResult(
                    chunk=original.chunk,
                    score=item.relevance_score,
                    document=original.document,
                )
            )

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "cohere reranking completed",
            query_length=len(query),
            candidates=len(results),
            top_k=top_k,
            results_count=len(reranked),
            model=self._model,
            duration_ms=round(duration_ms, 2),
        )

        return reranked


class CrossEncoderReranker(Reranker):
    """Re-ranks search results using a local cross-encoder model."""

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str | None = None):
        """Initialize the cross-encoder re-ranker.

        Args:
            model_name: HuggingFace model name. Defaults to ms-marco-MiniLM-L-6-v2.
        """
        self._model_name = model_name or self.DEFAULT_MODEL
        start = time.perf_counter()
        self._model = CrossEncoder(self._model_name)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "cross-encoder model loaded",
            model=self._model_name,
            duration_ms=round(duration_ms, 2),
        )

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        if not results:
            return []

        start = time.perf_counter()

        pairs = [(query, r.chunk.content) for r in results]
        scores = self._model.predict(pairs)

        scored = list(zip(scores, results))
        scored.sort(key=lambda x: x[0], reverse=True)
        scored = scored[:top_k]

        reranked = [
            SearchResult(
                chunk=result.chunk,
                score=float(score),
                document=result.document,
            )
            for score, result in scored
        ]

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "cross-encoder reranking completed",
            query_length=len(query),
            candidates=len(results),
            top_k=top_k,
            results_count=len(reranked),
            model=self._model_name,
            duration_ms=round(duration_ms, 2),
        )

        return reranked
