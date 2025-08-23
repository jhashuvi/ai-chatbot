"""
Common data structures used across multiple schemas.
These represent shared concepts like citations, context chunks, metrics,
and (optionally) embedding/index metadata for diagnostics.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from .base import BaseSchema


class EmbeddingInfo(BaseSchema):
    """
    Metadata about the embedding/index used during retrieval.
    Useful for debugging, audits, and ablation (e.g., switching models or metrics).
    """
    model: str = Field(..., description="Embedding model name, e.g. 'llama-text-embed-v2'")
    metric: Optional[Literal["cosine", "dot", "euclidean"]] = Field(
        "cosine", description="Similarity metric used by the index"
    )
    dimension: Optional[int] = Field(
        None, description="Embedding vector dimension (e.g., 1024, 2048, 768, 512, 384)"
    )
    namespace: Optional[str] = Field(None, description="Pinecone namespace used for the query")
    index_name: Optional[str] = Field(None, description="Pinecone index name")
    # Optional free-form mapping (e.g., Pinecone field_map)
    field_map: Optional[Dict[str, str]] = Field(
        None, description="Field map used by the index for integrated inference (e.g., {'text': 'text'})"
    )


class Citation(BaseSchema):
    """
    Represents a source citation for AI-generated responses.
    Flexible enough to accept either a rich citation or a minimal (id, score) pair.
    """
    # Preferred unique identifier for the chunk referenced
    chunk_id: Optional[str] = Field(
        None, description="Unique identifier for the source chunk (preferred)"
    )

    # Rich / optional metadata fields
    title: Optional[str] = Field(None, description="Title of the source document")
    snippet: Optional[str] = Field(None, description="Relevant text snippet from the source")
    source_url: Optional[HttpUrl] = Field(None, description="URL to the source document")
    relevance_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Normalized relevance score (0..1)"
    )

    # Minimal/legacy shape support (if you only have id/score)
    id: Optional[str] = Field(None, description="Generic identifier if chunk_id not provided")
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Raw similarity score")


class ContextChunk(BaseSchema):
    """
    Represents a chunk of context retrieved from the knowledge base (Pinecone).
    """
    chunk_id: str = Field(..., description="Unique identifier for this chunk (Pinecone record id)")
    content: str = Field(..., description="The text content of the chunk")
    source: str = Field(..., description="Source document this chunk came from (e.g., filename or doc id)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Original metadata stored alongside the chunk"
    )

    # Retrieval signal (normalized if possible). For cosine, many SDKs return 0..1; keep optional.
    score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Similarity score for this chunk"
    )

    # Optional category for UI filters (e.g., 'Account & Registration')
    category: Optional[str] = Field(None, description="Domain/category tag for this chunk")

    # Optional embedding/index info (model, metric, dimension, namespace)
    embedding: Optional[EmbeddingInfo] = Field(
        None, description="Embedding/index metadata for diagnostics"
    )


class ChatMetrics(BaseSchema):
    """
    Performance and analytics metrics for a single assistant turn.
    """
    # Token usage may not always be available; keep optional
    tokens_used: Optional[int] = Field(None, ge=0, description="Number of tokens used in the response")
    latency_ms: Optional[float] = Field(None, ge=0.0, description="End-to-end response latency in milliseconds")
    model_used: Optional[str] = Field(None, description="Generation model used (e.g., 'gpt-4o-mini')")
    retrieval_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Best/aggregate retrieval score for the turn"
    )
    context_chunks_used: int = Field(
        ..., ge=0, description="Number of context chunks included in the final prompt"
    )
    user_feedback: Optional[int] = Field(
        None, ge=-1, le=1, description="User feedback: 1 (thumbs up), -1 (thumbs down), 0 (neutral)"
    )

    # Optional embedding/index info for the turn (useful if you vary models/metrics)
    embedding: Optional[EmbeddingInfo] = Field(
        None, description="Embedding/index metadata applied for this turn"
    )


class ErrorResponse(BaseSchema):
    """
    Standard error response format for API errors.
    """
    error: str = Field(..., description="Human-readable error message")
    error_code: str = Field(..., description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(..., description="When the error occurred (ISO 8601)")
