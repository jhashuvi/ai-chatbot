import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # /Users/shuvijha/ai-chatbot/ai-chatbot
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX = os.getenv("PINECONE_INDEX", "")
    PINECONE_HOST = os.getenv("PINECONE_HOST", "")

    # JWT config
    JWT_SECRET = os.getenv("JWT_SECRET", "")
    JWT_ALG = os.getenv("JWT_ALG", "HS256")
    JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", 60))

settings = Settings()
