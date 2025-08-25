"""
Base model class that provides common fields for all database entities.
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
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # String representation for debugging purposes
    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"<{cls}(id={getattr(self, 'id', None)})>"
