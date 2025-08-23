"""
This file contains the configuration for the application (located in backend).
"""

import os

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX = os.getenv("PINECONE_INDEX", "")
    PINECONE_HOST = os.getenv("PINECONE_HOST", "")
    JWT_SECRET = os.getenv("JWT_SECRET", "change_me")

settings = Settings()
