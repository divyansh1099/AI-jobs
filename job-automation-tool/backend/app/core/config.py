from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # API Settings
    port: int = 3000
    host: str = "0.0.0.0"
    debug: bool = True
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/job_automation"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "job_automation"
    database_user: str = "postgres"
    database_password: str = "password"
    
    # Redis/Queue
    redis_url: str = "redis://localhost:6379"
    use_redis: bool = False  # Fallback to in-memory if Redis not available
    
    # MLX Settings
    model_path: str = "./models/"
    model_name: str = "llama-3.2-3b-instruct"
    max_tokens: int = 512
    
    # Browser Settings
    headless: bool = True
    browser_timeout: int = 30000
    
    # Application Settings
    max_concurrent_applications: int = 3
    rate_limit_delay: int = 5000
    max_retries: int = 3
    
    # Logging
    log_level: str = "INFO"
    log_path: str = "./logs/"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    
    # CORS
    allowed_origins: List[str] = ["http://localhost:3001", "http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()