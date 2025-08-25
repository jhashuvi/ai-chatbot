# app/schemas/user.py
"""
Pydantic schemas for User entity.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import EmailStr, Field

from .base import BaseSchema, BaseResponseSchema

class UserBase(BaseSchema):
    """
    Base user schema with common fields.
    """
    session_id: str = Field(..., description="Anonymous or authenticated session identifier")
    email: Optional[EmailStr] = Field(None, description="Email for authenticated users")
    is_authenticated: bool = Field(False, description="Whether the user is authenticated")


class UserCreate(BaseSchema):
    """
    Schema for creating new users.
    """
    session_id: str = Field(..., description="Browser/session identifier for the user")


class UserUpdate(BaseSchema):
    """
    Schema for updating user information.
    Used when upgrading anonymous users to authenticated users or
    updating existing user details like email or password.
    """
    # Authentication fields
    email: Optional[EmailStr] = None
    password_hash: Optional[str] = None  # Use password_hash to match DB and repository layer
    is_authenticated: Optional[bool] = None
    last_login_at: Optional[datetime] = None


class UserLogin(BaseSchema):
    """
    Schema for user login requests.
    """
    email: EmailStr
    password: str


class UserResponse(UserBase, BaseResponseSchema):
    """
    Complete user data returned to the frontend.
    """
    last_login_at: Optional[datetime] = None
