"""
User-related schemas for authentication and user management.
Handles both anonymous and authenticated users.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from .base import BaseResponseSchema

class UserCreate(BaseModel):
    """
    Schema for creating a new user (anonymous or authenticated).
    Supports the seamless flow from anonymous to authenticated users.
    """
    
    session_id: str = Field(..., min_length=1, max_length=255, description="Browser session identifier")
    email: Optional[EmailStr] = Field(None, description="Email address (required for authenticated users)")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Password (required for authenticated users)")
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password strength for authenticated users."""
        if v is not None:
            if len(v) < 8:
                raise ValueError('Password must be at least 8 characters long')
            if not any(c.isupper() for c in v):
                raise ValueError('Password must contain at least one uppercase letter')
            if not any(c.islower() for c in v):
                raise ValueError('Password must contain at least one lowercase letter')
            if not any(c.isdigit() for c in v):
                raise ValueError('Password must contain at least one digit')
        return v
    
    @validator('email', 'password')
    def validate_authentication_fields(cls, v, values):
        """Ensure both email and password are provided for authenticated users."""
        if 'email' in values and values['email'] is not None:
            if 'password' not in values or values['password'] is None:
                raise ValueError('Password is required when email is provided')
        if 'password' in values and values['password'] is not None:
            if 'email' not in values or values['email'] is None:
                raise ValueError('Email is required when password is provided')
        return v

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

class UserResponse(BaseResponseSchema):
    """
    Schema for user data in API responses.
    Hides sensitive information like password hashes.
    """
    
    session_id: str = Field(..., description="Browser session identifier")
    email: Optional[str] = Field(None, description="Email address (None for anonymous users)")
    is_authenticated: bool = Field(..., description="Whether the user has authenticated")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    
    class Config:
        # Exclude password_hash from responses for security
        exclude = {"password_hash"}

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
