# app/services/auth_service.py
"""
Authentication service for user registration, login, and session management.
Handles both anonymous user upgrades and traditional authentication flows.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, Dict
from uuid import uuid4
import logging
import os
from dataclasses import dataclass

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate

# Password hashing context using bcrypt for security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# --- AuthError for safe, classifiable failures ---
@dataclass
class AuthError(Exception):
    """
    Structured authentication error for safe client communication.
    """
    code: str                 # "NO_ACCOUNT" | "BAD_PASSWORD" | "UNEXPECTED"
    public_detail: str        # Safe message for clients
    log_detail: str = ""      # Extra info for server logs

class AuthService:
    """   
    Supports the dual user flow: anonymous users can start chatting immediately
    and upgrade to authenticated users later without losing their data.
    """
    
    def __init__(self, user_repo: Optional[UserRepository] = None):
        """Initialize with optional user repository for dependency injection."""
        self.user_repo = user_repo or UserRepository()

    # ---- Password Security Helpers ----
    def hash_password(self, password: str) -> str:
        """Hash a plain text password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        """Verify a plain text password against its hash."""
        return pwd_context.verify(plain, hashed)

    # ---- JWT Token Management ----
    def _create_access_token(self, data: dict, minutes: Optional[int] = None) -> str:
        """Create a JWT access token with configurable expiration."""
        # Use custom expiration or default from settings
        exp_min = minutes if minutes is not None else settings.JWT_EXPIRE_MIN
        
        # Create payload with expiration timestamp
        payload = data.copy()
        payload["exp"] = datetime.utcnow() + timedelta(minutes=exp_min)
        
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

    def verify(self, token: str) -> Optional[int]:
        """Verify and decode a JWT token, returning user ID if valid."""
        try:
            # Decode token and extract user ID from subject claim
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
            return int(payload.get("sub"))
        except (JWTError, ValueError):
            return None

    def authenticate(self, db: Session, email: str, password: str) -> Dict:
        """
        Authenticate a user with email and password.
        On failure, raises AuthError.
        """
        # Normalize email for consistent storage and lookup
        email_norm = email.strip().lower()
        user = self.user_repo.get_by_email(db, email_norm)

        logger.warning({
            "step": "authenticate_called",
            "email_input": email,
            "email_norm": email_norm,
            "user_found": bool(user),
            "has_password_hash": bool(getattr(user, "password_hash", None)) if user else None,
            "db_url": getattr(settings, "DATABASE_URL", None),
            "instance_id": os.getenv("INSTANCE_ID", "local"),
        })

        # Check if user exists and has a password hash
        if not user or not getattr(user, "password_hash", None):
            logger.warning({
                "step": "authenticate_failed",
                "reason": "user_not_found_or_no_hash",
                "email_norm": email_norm
            })
            raise AuthError(
                code="NO_ACCOUNT",
                public_detail="We couldn't find an account with that email.",
                log_detail=f"no user or no hash for {email_norm}",
            )

        # Verify the password against the stored hash
        try:
            ok = self.verify_password(password, user.password_hash)
        except Exception as e:
            logger.exception({"step": "authenticate_verify_exception", "email_norm": email_norm})
            raise AuthError(
                code="UNEXPECTED",
                public_detail="We couldn't sign you in. Please try again.",
                log_detail=str(e),
            )

        # Check if password verification succeeded
        if not ok:
            logger.warning({
                "step": "authenticate_failed",
                "reason": "bad_password",
                "user_id": user.id,
                "email_norm": email_norm
            })
            raise AuthError(
                code="BAD_PASSWORD",
                public_detail="Incorrect email or password.",
                log_detail=f"bad password for uid={user.id}",
            )

        # Authentication successful - update last login time
        self.user_repo.update_last_login(db, user)

        # Generate JWT access token for the authenticated user
        token = self._create_access_token({"sub": str(user.id)})
        
        # Log successful authentication
        logger.info({
            "step": "authenticate_success",
            "user_id": user.id,
            "email": user.email,
        })
        
        return {"user_id": user.id, "access_token": token, "token_type": "bearer"}

    def register_user(
        self,
        db: Session,
        email: str,
        password: str,
        *,
        session_id: Optional[str] = None,
    ):
        """
        Register a new user or upgrade an existing anonymous user.
        """
        # Normalize email for consistent storage and lookup
        email_norm = email.strip().lower()

        # Check for existing users with this email
        existing_by_email = self.user_repo.get_by_email(db, email_norm)
        
        # Look for anonymous user with the provided session ID
        anon_user = self.user_repo.get_by_session_id(db, session_id) if session_id else None

        # Prevent email collision with different users
        if existing_by_email and (not anon_user or existing_by_email.id != anon_user.id):
            raise ValueError("email_already_registered")

        hashed_pw = self.hash_password(password)
        
        update = UserUpdate(
            email=email_norm,
            password_hash=hashed_pw,
            is_authenticated=True,
            last_login_at=datetime.utcnow(),
        )

        # If anonymous user exists, upgrade them to authenticated
        if anon_user:
            return self.user_repo.update(db, anon_user, update)

        # Otherwise create a new user with fresh session ID
        new_sid = str(uuid4())
        user = self.user_repo.create(db, {"session_id": new_sid})
        return self.user_repo.update(db, user, update)
