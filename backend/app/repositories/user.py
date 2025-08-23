"""
User repository for user management operations.
Handles both anonymous and authenticated users with session-based tracking.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from .base import BaseRepository
from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """
    Repository for user management operations.
    Extends BaseRepository with user-specific functionality.
    """
    
    def __init__(self):
        super().__init__(User)
    
    def get_by_session_id(self, db: Session, session_id: str) -> Optional[User]:
        """
        Get user by browser session identifier.
        Works for both anonymous and authenticated users.
        
        Args:
            db: Database session
            session_id: Browser session identifier
            
        Returns:
            User instance or None if not found
        """
        try:
            return db.query(User).filter(User.session_id == session_id).first()
        except Exception as e:
            logger.error(f"Error getting user by session_id {session_id}: {e}")
            raise
    
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Get user by email address.
        Only works for authenticated users.
        
        Args:
            db: Database session
            email: User's email address
            
        Returns:
            User instance or None if not found
        """
        try:
            return db.query(User).filter(User.email == email).first()
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            raise
    
    def get_authenticated_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all authenticated users with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of authenticated users
        """
        try:
            return db.query(User).filter(
                User.is_authenticated == True
            ).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting authenticated users: {e}")
            raise
    
    def get_anonymous_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Get all anonymous users with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of anonymous users
        """
        try:
            return db.query(User).filter(
                User.is_authenticated == False
            ).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting anonymous users: {e}")
            raise
    
    def create_anonymous_user(self, db: Session, session_id: str) -> User:
        """
        Create a new anonymous user.
        
        Args:
            db: Database session
            session_id: Browser session identifier
            
        Returns:
            Created anonymous user
        """
        try:
            user_data = UserCreate(session_id=session_id)
            return self.create(db, user_data)
        except Exception as e:
            logger.error(f"Error creating anonymous user with session_id {session_id}: {e}")
            raise
    
    def authenticate_user(self, db: Session, user: User, email: str, password_hash: str) -> User:
        """
        Convert anonymous user to authenticated user.
        
        Args:
            db: Database session
            user: Existing user instance
            email: User's email address
            password_hash: Hashed password
            
        Returns:
            Updated authenticated user
        """
        try:
            update_data = UserUpdate(
                email=email,
                password=password_hash  # This will be hashed by the service layer
            )
            return self.update(db, user, update_data)
        except Exception as e:
            logger.error(f"Error authenticating user {user.id}: {e}")
            raise
    
    def update_last_login(self, db: Session, user: User) -> User:
        """
        Update user's last login timestamp.
        
        Args:
            db: Database session
            user: User instance to update
            
        Returns:
            Updated user
        """
        try:
            from datetime import datetime
            user.last_login_at = datetime.utcnow()
            db.add(user)
            db.flush()
            db.refresh(user)
            
            logger.info(f"Updated last login for user {user.id}")
            return user
        except Exception as e:
            logger.error(f"Error updating last login for user {user.id}: {e}")
            db.rollback()
            raise
    
    def get_or_create_user(self, db: Session, session_id: str) -> User:
        """
        Get existing user or create new anonymous user.
        Handles the seamless anonymous user flow.
        
        Args:
            db: Database session
            session_id: Browser session identifier
            
        Returns:
            User instance (existing or newly created)
        """
        try:
            # Try to find existing user
            user = self.get_by_session_id(db, session_id)
            
            if user:
                # Update last login for returning users
                user = self.update_last_login(db, user)
                logger.info(f"Found existing user {user.id} for session {session_id}")
                return user
            else:
                # Create new anonymous user
                user = self.create_anonymous_user(db, session_id)
                logger.info(f"Created new anonymous user {user.id} for session {session_id}")
                return user
        except Exception as e:
            logger.error(f"Error in get_or_create_user for session {session_id}: {e}")
            raise
    
    def count_by_authentication_status(self, db: Session) -> dict:
        """
        Get user counts by authentication status.
        Useful for analytics and monitoring.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with counts
        """
        try:
            total_users = self.count(db)
            authenticated_users = self.count(db, {"is_authenticated": True})
            anonymous_users = self.count(db, {"is_authenticated": False})
            
            return {
                "total": total_users,
                "authenticated": authenticated_users,
                "anonymous": anonymous_users
            }
        except Exception as e:
            logger.error(f"Error counting users by authentication status: {e}")
            raise
