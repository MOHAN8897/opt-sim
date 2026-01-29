from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import json

class Settings(BaseSettings):
    # App - SECRET_KEY is REQUIRED (no fallback)
    SECRET_KEY: str = Field(..., description="Secret key for JWT - MUST be set in .env")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 hours
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]
    FRONTEND_URL: str = "http://localhost:8080"

    # Google
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_AUTH_URI: str
    GOOGLE_TOKEN_URI: str
    GOOGLE_USERINFO_URI: str

    # Upstox
    UPSTOX_API_KEY: str
    UPSTOX_API_SECRET: str
    UPSTOX_REDIRECT_URI: str = "http://localhost:5173/connect-broker" # Frontend Callback

    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    class Config:
        env_file = "C:/Users/subha/OneDrive/Desktop/simulator/.env"
        extra = "ignore"

settings = Settings()
