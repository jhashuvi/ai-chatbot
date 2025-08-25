"""
User repository for user management operations.
"""

from __future__ import annotations
from typing import Optional, List, Tuple
from datetime import datetime
import logging

from sqlalchemy import and_, or_, func, text
from sqlalchemy.orm import Session

from .base import BaseRepository
from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self) -> None:
        super().__init__(User)


    def create(self, db: Session, data: UserCreate) -> User:
        """Create and persist a User. ALWAYS commits and refreshes."""
        try:
            # Create user object from Pydantic schema
            obj = User(**data.model_dump())
            db.add(obj)
            
            # Always commit immediately to avoid half-written rows in case of DB errors
            db.commit()
            db.refresh(obj)
            
            # Log successful creation for debugging and audit trails
            logger.debug({"repo": "user.create", "id": obj.id, "session_id": obj.session_id, "email": obj.email})
            return obj
        except Exception as e:
            db.rollback()
            logger.exception("Error in UserRepository.create")
            raise

    def update(self, db: Session, obj: User, data: UserUpdate) -> User:
        """Update and persist a User. ALWAYS commits and refreshes."""
        try:
            # Only update fields that are actually provided (exclude_unset=True)
            # This prevents accidentally overwriting fields with None
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(obj, k, v)
            
            # Add the user to the database
            db.add(obj)

            # Commit the changes to the database
            db.commit()
            db.refresh(obj)

            # Log the update for debugging and audit trails
            logger.debug({"repo": "user.update", "id": obj.id, "session_id": obj.session_id, "email": obj.email})
            return obj
        except Exception as e:
            db.rollback()
            logger.exception("Error in UserRepository.update")
            raise

    def get_by_session_id(self, db: Session, session_id: str) -> Optional[User]:
        """Get user by browser session identifier (works for anon and authed)."""
        try:
            # This is the primary way to identify users in the current system
            # Works for both anonymous (browser session) and authenticated users
            return db.query(User).filter(User.session_id == session_id).first()
        except Exception as e:
            logger.error(f"Error getting user by session_id {session_id}: {e}")
            raise

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email (normalized, case-insensitive)."""
        try:
            email_norm = email.strip().lower()
            return (
                db.query(User)
                .filter(func.lower(User.email) == email_norm)
                .first()
            )
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            raise

    def get_authenticated_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Get paginated list of authenticated users."""
        try:
            # Filter for users who have completed email/password registration
            return (
                db.query(User)
                .filter(User.is_authenticated.is_(True))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.error(f"Error getting authenticated users: {e}")
            raise

    def get_anonymous_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Get paginated list of anonymous users."""
        try:
            # Filter for users who haven't registered yet (browser session only)
            return (
                db.query(User)
                .filter(User.is_authenticated.is_(False))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.error(f"Error getting anonymous users: {e}")
            raise


    def create_anonymous_user(self, db: Session, session_id: str) -> User:
        """Create a new anonymous user (email/password_hash remain NULL)."""
        try:
            # Create user with only session_id - no email or password yet
            # This allows users to start using the chatbot immediately
            user_data = UserCreate(session_id=session_id)
            return self.create(db, user_data)
        except Exception as e:
            logger.error(f"Error creating anonymous user with session_id {session_id}: {e}")
            raise

    def authenticate_user(self, db: Session, user: User, email: str, password_hash: str) -> User:
        """Upgrade anonymous user -> authenticated user."""
        try:
            # Convert anonymous user to authenticated user
            # Sets email (normalized), password hash, and authentication flags
            update_data = UserUpdate(
                email=email.strip().lower(),  # Normalize email storage
                password_hash=password_hash,  # Store hashed password
                is_authenticated=True,        # Mark as authenticated
                last_login_at=datetime.utcnow(),  # Track login time
            )
            return self.update(db, user, update_data)
        except Exception as e:
            logger.error(f"Error authenticating user {getattr(user, 'id', None)}: {e}")
            raise

    def update_last_login(self, db: Session, user: User) -> User:
        """Touch last_login_at; persist with commit+refresh (no flush-only)."""
        try:
            # Update the last login timestamp for activity tracking
            user.last_login_at = datetime.utcnow()
            db.add(user)
            
            # Always commit immediately for login tracking
            db.commit()
            db.refresh(user)
            
            logger.info(f"Updated last login for user {user.id}")
            return user
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating last login for user {getattr(user, 'id', None)}: {e}")
            raise

    def get_or_create_user(self, db: Session, session_id: str) -> User:
        """Get existing user or create a new anonymous user for the given session_id."""
        try:
            # First, try to find an existing user for this session
            user = self.get_by_session_id(db, session_id)
            if user:
                # User exists - update their last login time
                user = self.update_last_login(db, user)
                logger.info(f"Found existing user {user.id} for session {session_id}")
                return user
            
            # No user found - create a new anonymous user
            # This enables immediate chatbot usage without registration
            user = self.create_anonymous_user(db, session_id)
            logger.info(f"Created new anonymous user {user.id} for session {session_id}")
            return user
        except Exception as e:
            logger.error(f"Error in get_or_create_user for session {session_id}: {e}")
            raise

    # -------- debugging --------

    def where_am_i(self, db: Session) -> Tuple[str, str, int]:
        """Returns (database, server_addr, server_port) for forensic logging."""
        # Useful for debugging connection issues and multi-database setups
        row = db.execute(text("SELECT current_database(), inet_server_addr(), inet_server_port()")).first()
        return (row[0], str(row[1]), int(row[2])) if row else ("", "", 0)

    def count_by_authentication_status(self, db: Session) -> dict:
        """Get counts for quick analytics."""
        try:
            # Get total user counts for dashboard and monitoring
            total_users = self.count(db)
            authenticated_users = self.count(db, {"is_authenticated": True})
            anonymous_users = self.count(db, {"is_authenticated": False})
            
            return {
                "total": total_users,
                "authenticated": authenticated_users,
                "anonymous": anonymous_users,
            }
        except Exception as e:
            logger.error(f"Error counting users by authentication status: {e}")
            raise