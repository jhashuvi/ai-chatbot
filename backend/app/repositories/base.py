"""
Base repository class with common CRUD operations.
Provides a consistent interface for all data access operations.
"""

from typing import TypeVar, Generic, Type, Optional, List, Any, Dict
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
        """
        Initialize repository with a specific model.
        
        Args:
            model: SQLAlchemy model class
        """
        self.model = model
    
    def get(self, db: Session, id: int) -> Optional[T]:
        """
        Get a single record by ID.
        
        Args:
            db: Database session
            id: Record ID
            
        Returns:
            Model instance or None if not found
        """
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
        """
        Get multiple records with pagination and filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of field filters
            
        Returns:
            List of model instances
        """
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
    
    def create(self, db: Session, obj_in: CreateSchemaType) -> T:
        """
        Create a new record.
        
        Args:
            db: Database session
            obj_in: Pydantic schema with creation data
            
        Returns:
            Created model instance
        """
        try:
            # Convert Pydantic schema to dict, excluding unset fields
            obj_data = obj_in.model_dump(exclude_unset=True)
            db_obj = self.model(**obj_data)
            
            db.add(db_obj)
            db.flush()  # Flush to get the ID
            db.refresh(db_obj)
            
            logger.info(f"Created {self.model.__name__} with id {db_obj.id}")
            return db_obj
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            db.rollback()
            raise
    
    def update(
        self, 
        db: Session, 
        db_obj: T, 
        obj_in: UpdateSchemaType
    ) -> T:
        """
        Update an existing record.
        
        Args:
            db: Database session
            db_obj: Existing model instance
            obj_in: Pydantic schema with update data
            
        Returns:
            Updated model instance
        """
        try:
            # Convert Pydantic schema to dict, excluding unset fields
            update_data = obj_in.model_dump(exclude_unset=True)
            
            # Update only provided fields
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
        """
        Delete a record by ID.
        
        Args:
            db: Database session
            id: Record ID
            
        Returns:
            True if deleted, False if not found
        """
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
        """
        Count records with optional filtering.
        
        Args:
            db: Database session
            filters: Dictionary of field filters
            
        Returns:
            Number of matching records
        """
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
        """
        Check if a record exists by ID.
        
        Args:
            db: Database session
            id: Record ID
            
        Returns:
            True if exists, False otherwise
        """
        try:
            return db.query(self.model).filter(self.model.id == id).first() is not None
        except Exception as e:
            logger.error(f"Error checking existence of {self.model.__name__} with id {id}: {e}")
            raise
