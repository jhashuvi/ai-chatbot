# app/routers/auth.py
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthService
from app.repositories.user import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- DI ----
def get_auth_service() -> AuthService:
    return AuthService()

def get_user_repo() -> UserRepository:
    return UserRepository()

# ---- Schemas ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterResponse(BaseModel):
    user_id: int
    access_token: str
    token_type: str = "bearer"
    # Echo current session id so frontend can keep/stitch if it changed
    session_id: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    user_id: int
    access_token: str
    token_type: str = "bearer"

class MeResponse(BaseModel):
    user_id: int
    email: Optional[EmailStr] = None
    is_authenticated: bool = True

# ---- Helpers ----
def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return token

# ---- Routes ----
@router.post("/register", response_model=RegisterResponse, summary="Register or upgrade anonymous user")
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    auth: AuthService = Depends(get_auth_service),
    user_repo: UserRepository = Depends(get_user_repo),
    x_session_id: Optional[str] = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
):
    """
    - If X-Session-Id corresponds to an anonymous user, upgrade that record in-place.
    - Otherwise create a new user with a fresh UUID session_id.
    - Duplicate email (owned by a different user) -> 409 Conflict.
    """
    try:
        user = auth.register_user(db, payload.email, payload.password, session_id=x_session_id)
    except ValueError as e:
        if str(e) == "email_already_registered":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        raise

    # Mint an access token for immediate use
    token = auth._create_access_token({"sub": str(user.id)})
    # Ensure we return the effective session_id for the client to persist
    return RegisterResponse(
        user_id=user.id,
        access_token=token,
        token_type="bearer",
        session_id=getattr(user, "session_id", x_session_id or ""),
    )

@router.post("/login", response_model=LoginResponse, summary="Login and receive an access token")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    auth: AuthService = Depends(get_auth_service),
):
    result = auth.authenticate(db, payload.email, payload.password)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return LoginResponse(**result)

@router.get("/me", response_model=MeResponse, summary="Return the current authenticated identity")
def me(
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repo),
    auth: AuthService = Depends(get_auth_service),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    token = _extract_bearer(authorization)
    user_id = auth.verify(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = user_repo.get(db, user_id)
    return MeResponse(user_id=user_id, email=getattr(user, "email", None), is_authenticated=True)
