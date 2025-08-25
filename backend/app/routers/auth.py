# app/routers/auth.py
"""
Authentication router for user registration, login, and identity verification.
Handles both anonymous user upgrades and traditional authentication flows.
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthService, AuthError
from app.repositories.user import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- Dependency Injection ----
def get_auth_service() -> AuthService:
    """Get a new AuthService for this request."""
    return AuthService()

def get_user_repo() -> UserRepository:
    """Get a new UserRepository for this request."""
    return UserRepository()

# ---- Request/Response Schemas ----
class RegisterRequest(BaseModel):
    """User registration request with email and password."""
    email: EmailStr
    password: str

class RegisterResponse(BaseModel):
    """Successful registration response with user details and access token."""
    user_id: int
    access_token: str
    token_type: str = "bearer"
    session_id: str  # Browser session ID for continued anonymous usage

class LoginRequest(BaseModel):
    """User login request with email and password."""
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    """Successful login response with user ID and access token."""
    user_id: int
    access_token: str
    token_type: str = "bearer"

class MeResponse(BaseModel):
    """Current user identity information."""
    user_id: int
    email: Optional[EmailStr] = None  # May be None for anonymous users
    is_authenticated: bool = True

# ---- Helper Functions ----
def _extract_bearer(authorization: Optional[str]) -> str:
    """Extract bearer token from Authorization header with proper error handling."""
    # Check if Authorization header exists and starts with "Bearer "
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    
    # Extract the token part after "Bearer "
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    
    return token

# ---- API Routes ----
@router.post("/register", response_model=RegisterResponse, summary="Register or upgrade anonymous user")
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    auth: AuthService = Depends(get_auth_service),
    user_repo: UserRepository = Depends(get_user_repo),
    x_session_id: Optional[str] = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
):
    """
    Register a new user or upgrade an existing anonymous user.
    
    This endpoint handles both scenarios:
    1. New user registration with email/password
    2. Upgrading anonymous user (identified by X-Session-Id) to authenticated user
    """
    try:
        # Attempt to register/upgrade the user
        user = auth.register_user(db, payload.email, payload.password, session_id=x_session_id)
    except ValueError as e:
        # Handle specific registration errors
        if str(e) == "email_already_registered":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        raise

    # Generate JWT access token for the newly registered user
    token = auth._create_access_token({"sub": str(user.id)})
    
    # Return user details with access token and session ID
    # session_id helps frontend maintain the browser session context
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
    """
    Authenticate existing user and provide access token.
    
    Security note: Always returns 401 to prevent account enumeration attacks.
    Error details are provided via X-Error-Code header for better UX.
    """
    try:
        # Attempt to authenticate the user
        result = auth.authenticate(db, payload.email, payload.password)
        return LoginResponse(**result)
    except AuthError as e:
        # Always return 401 to avoid account enumeration, but include error code for UX
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.public_detail,
            headers={"X-Error-Code": e.code},  # Safe error code for frontend branching
        )

@router.get("/me", response_model=MeResponse, summary="Return the current authenticated identity")
def me(
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repo),
    auth: AuthService = Depends(get_auth_service),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """
    Get current user identity from JWT token.
    """
    # Extract and validate the bearer token
    token = _extract_bearer(authorization)
    
    # Verify the token and extract user ID
    user_id = auth.verify(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Fetch user details from database
    user = user_repo.get(db, user_id)
    
    # Return user identity information
    return MeResponse(user_id=user_id, email=getattr(user, "email", None), is_authenticated=True)
