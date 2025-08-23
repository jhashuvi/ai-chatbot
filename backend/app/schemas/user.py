# app/schemas/user.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import EmailStr, Field

from .base import BaseSchema, BaseResponseSchema


class UserBase(BaseSchema):
    session_id: str = Field(..., description="Anonymous or authenticated session identifier")
    email: Optional[EmailStr] = Field(None, description="Email for authenticated users")
    is_authenticated: bool = Field(False, description="Whether the user is authenticated")


class UserCreate(BaseSchema):
    session_id: str = Field(..., description="Browser/session identifier for the user")


class UserUpdate(BaseSchema):
    # Use password_hash here to match the DB and repository layer
    email: Optional[EmailStr] = None
    password_hash: Optional[str] = None
    is_authenticated: Optional[bool] = None
    last_login_at: Optional[datetime] = None


class UserLogin(BaseSchema):
    # Handy if/when you add an auth endpoint
    email: EmailStr
    password: str


class UserResponse(UserBase, BaseResponseSchema):
    last_login_at: Optional[datetime] = None
