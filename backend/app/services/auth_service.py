# app/services/auth_service.py
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, Dict
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, user_repo: Optional[UserRepository] = None):
        self.user_repo = user_repo or UserRepository()

    # ---- password helpers ----
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    # ---- JWT helpers ----
    def _create_access_token(self, data: dict, minutes: Optional[int] = None) -> str:
        exp_min = minutes if minutes is not None else settings.JWT_EXPIRE_MIN
        payload = data.copy()
        payload["exp"] = datetime.utcnow() + timedelta(minutes=exp_min)
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

    def verify(self, token: str) -> Optional[int]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
            return int(payload.get("sub"))
        except (JWTError, ValueError):
            return None

    # ---- high-level auth ----
    def authenticate(self, db: Session, email: str, password: str) -> Optional[Dict]:
        email_norm = email.strip().lower()
        user = self.user_repo.get_by_email(db, email_norm)
        if not user or not getattr(user, "password_hash", None):
            return None
        if not self.verify_password(password, user.password_hash):
            return None

        # touch last_login
        self.user_repo.update_last_login(db, user)

        token = self._create_access_token({"sub": str(user.id)})
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
        Registration/upgrade rules:
        - Normalize email (lowercase).
        - If anon user exists for session_id -> upgrade that record (no migration).
        - Otherwise create new user with a fresh UUID session_id.
        - Prevent duplicate email collisions:
            * If email already belongs to a *different* user than the anon session, raise ValueError("email_already_registered").
        """
        email_norm = email.strip().lower()

        # Lookups we need
        existing_by_email = self.user_repo.get_by_email(db, email_norm)
        anon_user = self.user_repo.get_by_session_id(db, session_id) if session_id else None

        # If email is taken by another user (not the same anon we're upgrading) -> block
        if existing_by_email and (not anon_user or existing_by_email.id != anon_user.id):
            raise ValueError("email_already_registered")

        hashed_pw = self.hash_password(password)
        update = UserUpdate(
            email=email_norm,
            password_hash=hashed_pw,
            is_authenticated=True,
            last_login_at=datetime.utcnow(),
        )

        if anon_user:
            # upgrade in place
            return self.user_repo.update(db, anon_user, update)

        # No anon session or not found -> create a fresh user with a new UUID session_id
        new_sid = str(uuid4())
        user = self.user_repo.create(db, {"session_id": new_sid})
        return self.user_repo.update(db, user, update)
