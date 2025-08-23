"""
Common data structures used across multiple schemas.
These represent shared concepts like citations, context chunks, and metrics.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from .base import BaseSchema

class Citation(BaseSchema):
    """
    Represents a source citation for AI-generated responses.
    Used to provide transparency about information sources.
    """
    
    title: str = Field(..., description="Title of the source document")
    snippet: str = Field(..., description="Relevant text snippet from the source")
    source_url: Optional[HttpUrl] = Field(None, description="URL to the source document")
    chunk_id: str = Field(..., description="Unique identifier for the source chunk")
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="How relevant this source is to the query")

class ContextChunk(BaseSchema):
    """
    Represents a chunk of context retrieved from the knowledge base.
    Used in RAG responses to show what information was used.
    """
    
    content: str = Field(..., description="The actual text content of the chunk")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the chunk")
    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    source: str = Field(..., description="Source document this chunk came from")
    category: Optional[str] = Field(None, description="Category of the source (e.g., 'Account & Registration')")

class ChatMetrics(BaseSchema):
    """
    Performance and analytics metrics for chat interactions.
    Used for monitoring and optimization.
    """
    
    tokens_used: int = Field(..., ge=0, description="Number of tokens used in the response")
    latency_ms: float = Field(..., ge=0.0, description="Response time in milliseconds")
    model_used: str = Field(..., description="AI model used for generation (e.g., 'gpt-4')")
    retrieval_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Quality score of retrieved context")
    context_chunks_used: int = Field(..., ge=0, description="Number of context chunks used")
    user_feedback: Optional[int] = Field(None, ge=-1, le=1, description="User feedback: 1 (thumbs up), -1 (thumbs down), 0 (neutral)")

class ErrorResponse(BaseSchema):
    """
    Standard error response format for API errors.
    Ensures consistent error handling across the application.
    """
    
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="When the error occurred")
