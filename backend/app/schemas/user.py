"""
User-related schemas for authentication and user management.
Handles both anonymous and authenticated users.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator, ConfigDict
from .base import BaseResponseSchema


class UserCreate(BaseModel):
    """
    Schema for creating a new user (anonymous or authenticated).
    Supports the seamless flow from anonymous to authenticated users.
    """

    # Browser/device identifier for anonymous flow (kept as str for flexibility)
    session_id: str = Field(..., min_length=1, max_length=255, description="Browser session identifier")

    # If either email or password is provided, both must be provided
    email: Optional[EmailStr] = Field(None, description="Email address (required for authenticated users)")
    password: Optional[str] = Field(
        None, min_length=8, max_length=128, description="Password (required for authenticated users)"
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if not any(c.isupper() for c in v):
                raise ValueError("Password must contain at least one uppercase letter")
            if not any(c.islower() for c in v):
                raise ValueError("Password must contain at least one lowercase letter")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one digit")
        return v

    @model_validator(mode="after")
    def validate_authentication_fields(self):
        # Enforce both-or-neither rule for email/password
        if (self.email is None) ^ (self.password is None):
            raise ValueError("Email and password must be provided together for authentication")
        return self


class UserLogin(BaseModel):
    """
    Schema for user login authentication.
    Used when anonymous users want to authenticate.
    """

    session_id: str = Field(..., description="Existing browser session identifier")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")


class UserUpdate(BaseModel):
    """
    Schema for updating user information.
    Allows users to modify their profile.
    """

    email: Optional[EmailStr] = Field(None, description="New email address")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="New password")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if not any(c.isupper() for c in v):
                raise ValueError("Password must contain at least one uppercase letter")
            if not any(c.islower() for c in v):
                raise ValueError("Password must contain at least one lowercase letter")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(BaseResponseSchema):
    """
    Schema for user data in API responses.
    Hides sensitive information like password hashes.
    """

    # NOTE: This is the anonymous/returning browser identifier (not a chat session id)
    session_id: str = Field(..., description="Browser session identifier")
    email: Optional[str] = Field(None, description="Email address (None for anonymous users)")
    is_authenticated: bool = Field(..., description="Whether the user has authenticated")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")

    # Pydantic v2: allow building from ORM objects (SQLAlchemy)
    model_config = ConfigDict(from_attributes=True)


class UserSession(BaseModel):
    """
    Schema for user session information.
    Used for session management and authentication.
    """

    session_id: str = Field(..., description="Browser session identifier")
    user_id: int = Field(..., description="User ID")
    is_authenticated: bool = Field(..., description="Authentication status")
    expires_at: datetime = Field(..., description="When the session expires")


class AuthResponse(BaseModel):
    """
    Schema for authentication responses.
    Returns user info and JWT token for authenticated users.
    """

    user: UserResponse = Field(..., description="User information")
    access_token: Optional[str] = Field(None, description="JWT access token (for authenticated users)")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: Optional[int] = Field(None, description="Token expiration time in seconds")
