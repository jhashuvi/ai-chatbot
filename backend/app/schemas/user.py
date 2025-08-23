"""
Pydantic schemas for User entity.
Aligned with models.user.User and repositories.user.UserRepository.
"""

from typing import Optional
from datetime import datetime
from pydantic import Field, EmailStr

from .base import BaseSchema, BaseResponseSchema


class UserCreate(BaseSchema):
    session_id: str = Field(..., description="Anonymous or authenticated session key")
    # Optional immediate-auth fields
    email: Optional[EmailStr] = None
    password_hash: Optional[str] = Field(
        None, description="Hashed password; service layer should hash plain text first"
    )
    is_authenticated: Optional[bool] = False


class UserUpdate(BaseSchema):
    email: Optional[EmailStr] = None
    password_hash: Optional[str] = Field(
        None, description="Set only with a properly hashed password"
    )
    is_authenticated: Optional[bool] = None
    last_login_at: Optional[datetime] = None


class UserResponse(BaseResponseSchema):
    session_id: str
    email: Optional[EmailStr] = None
    is_authenticated: bool
    last_login_at: Optional[datetime] = None
