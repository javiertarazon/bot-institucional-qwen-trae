"""
CIP Lite - Core Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configuración principal de CIP Lite."""
    
    # API Keys
    deepseek_api_key: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "cip-lite-bot/1.0"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # DuckDB
    duckdb_path: str = "./data/cip_lite.duckdb"
    
    # Logging
    log_level: str = "INFO"
    
    # Feature Flags
    enable_onchain: bool = True
    enable_paper_trading: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
