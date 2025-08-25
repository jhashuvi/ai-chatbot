"""
Base repository class that provides a consistent interface for all data access operations.
"""

from typing import TypeVar, Generic, Type, Optional, List, Any, Dict, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel
import logging

from ..models.base import BaseModel as DBBaseModel

# Type variables for generic repository
T = TypeVar('T', bound=DBBaseModel)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)

logger = logging.getLogger(__name__)

class BaseRepository(Generic[T, CreateSchemaType, UpdateSchemaType]):
    """
    Base repository with common CRUD operations.
    
    Generic types:
    - T: Database model type
    - CreateSchemaType: Pydantic schema for creation
    - UpdateSchemaType: Pydantic schema for updates
    """
    
    def __init__(self, model: Type[T]):
        """Initialize repository with a specific model."""
        self.model = model
    
    def get(self, db: Session, id: int) -> Optional[T]:
        """Get a single record by ID."""
        try:
            return db.query(self.model).filter(self.model.id == id).first()
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} with id {id}: {e}")
            raise
    
    def get_multi(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        """Get multiple records with pagination and filtering."""
        try:
            query = db.query(self.model)
            
            # Apply filters if provided
            if filters:
                filter_conditions = []
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        filter_conditions.append(getattr(self.model, field) == value)
                
                if filter_conditions:
                    query = query.filter(and_(*filter_conditions))
            
            return query.offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting multiple {self.model.__name__}: {e}")
            raise
    
    
    def create(self, db: Session, obj_in: Union[CreateSchemaType, dict]) -> T:
        """Create a new record in the database."""
        try:
            obj_data = self._to_dict(obj_in)
            obj_data = self._filter_model_fields(obj_data)
            db_obj = self.model(**obj_data)
            db.add(db_obj)
            db.flush()
            db.refresh(db_obj)
            logger.info(f"Created {self.model.__name__} with id {db_obj.id}")
            return db_obj
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            db.rollback()
            raise

    def update(self, db: Session, db_obj: T, obj_in: Union[UpdateSchemaType, dict]) -> T:
        """Update an existing record in the database."""
        try:
            update_data = self._to_dict(obj_in)
            update_data = self._filter_model_fields(update_data)
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            db.add(db_obj)
            db.flush()
            db.refresh(db_obj)
            logger.info(f"Updated {self.model.__name__} with id {db_obj.id}")
            return db_obj
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} with id {db_obj.id}: {e}")
            db.rollback()
            raise

    def delete(self, db: Session, id: int) -> bool:
        """Delete a record by ID."""
        try:
            db_obj = db.query(self.model).filter(self.model.id == id).first()
            if db_obj:
                db.delete(db_obj)
                db.flush()
                logger.info(f"Deleted {self.model.__name__} with id {id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting {self.model.__name__} with id {id}: {e}")
            db.rollback()
            raise
    
    def count(self, db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering."""
        try:
            query = db.query(self.model)
            
            # Apply filters if provided
            if filters:
                filter_conditions = []
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        filter_conditions.append(getattr(self.model, field) == value)
                
                if filter_conditions:
                    query = query.filter(and_(*filter_conditions))
            
            return query.count()
        except Exception as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            raise
    
    def exists(self, db: Session, id: int) -> bool:
        """Check if a record exists by ID."""
        try:
            return db.query(self.model).filter(self.model.id == id).first() is not None
        except Exception as e:
            logger.error(f"Error checking existence of {self.model.__name__} with id {id}: {e}")
            raise
    
    def _filter_model_fields(self, data: dict) -> dict:
        """Filter data to only include valid model fields."""
        cols = {c.key for c in self.model.__table__.columns}
        return {k: v for k, v in data.items() if k in cols}

    def _to_dict(self, obj: Any) -> dict:
        """Convert Pydantic model or dict to dictionary."""
        # Pydantic v2
        if hasattr(obj, "model_dump"):
            return obj.model_dump(exclude_unset=True)
        # Pydantic v1
        if hasattr(obj, "dict"):
            return obj.dict(exclude_unset=True)
        # Already a dict
        if isinstance(obj, dict):
            return obj
        raise TypeError(f"Unsupported input type for {self.model.__name__}: {type(obj)}")