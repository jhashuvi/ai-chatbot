"""
Base schemas that provide common fields and validation patterns.
These are used as building blocks for other schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class BaseSchema(BaseModel):
    """
    Base schema with common configuration for all schemas.
    
    Features:
    - Automatic JSON serialization
    - Case-insensitive field matching
    - Extra fields are ignored (security)
    - Automatic validation
    """
    
    model_config = ConfigDict(
        # Convert to JSON automatically
        json_encoders={
            datetime: lambda v: v.isoformat()
        },
        # Ignore extra fields (security)
        extra="ignore",
        # Case-insensitive field matching
        str_strip_whitespace=True,
        # Validate on assignment
        validate_assignment=True
    )

class TimestampSchema(BaseSchema):
    """
    Schema with automatic timestamp fields.
    Used for responses that include creation/update times.
    """
    created_at: datetime = Field(..., description="When the record was created")
    updated_at: datetime = Field(..., description="When the record was last updated")

class IDSchema(BaseSchema):
    """
    Schema with an ID field.
    Used for responses that include database IDs.
    """
    id: int = Field(..., description="Unique identifier for the record")

class BaseResponseSchema(TimestampSchema, IDSchema):
    """
    Base response schema with both ID and timestamp fields.
    Used for most API responses.
    """
    pass
