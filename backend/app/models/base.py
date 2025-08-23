"""
Base model class that provides common fields for all database entities.
This ensures consistency across our models and provides audit trails.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

# Create the base class for all our models
Base = declarative_base()

class BaseModel(Base):
    """
    Abstract base model that provides common fields for all entities.
    
    Attributes:
        id: Primary key for the entity
        created_at: Timestamp when the record was created
        updated_at: Timestamp when the record was last updated
    """
    
    # This makes this class abstract - it won't create a table
    __abstract__ = True
    
    # Primary key - auto-incrementing integer
    id = Column(Integer, primary_key=True, index=True)
    
    # Audit timestamps - automatically managed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
