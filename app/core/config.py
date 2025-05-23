from functools import lru_cache
from typing import Optional
from loguru import logger
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path
import os

# Determine the project root directory relative to this file
# config.py -> app/core/ -> app/ -> project_root
project_root = Path(__file__).resolve().parent.parent.parent
dotenv_path = project_root / ".env"
logger.debug(f"Expected .env path: {dotenv_path}")

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database settings
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DB_SERVER: str ="EMRE"
    DB_DATABASE: str = "MOODMOVIES"
    DB_USERNAME: Optional[str] = None   
    DB_PASSWORD: Optional[str] = None
    
    # API settings
    GEMINI_API_KEY: str  # Varsayılan değer kaldırıldı
    API_KEY: str  # API güvenlik anahtarı
    WEBHOOK_SECRET: str  # Webhook imzalama anahtarı
    
    # Application settings
    DEFINITIONS_PATH: str = "app/static/definitions.json"
    
    # Personality score normalization parameters
    # T-score calculation values: T = 50 + 10 * z
    # Raw score to Z-score transformation: z = (raw - mean) / std_dev
    PERSONALITY_MEAN: float = 3.0
    PERSONALITY_STD_DEV: float = 0.5
    
    # Gemini API settings
    GEMINI_MODEL: str = "gemini-2.0-flash-thinking-exp-01-21"
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FULL_GEMINI_IO: bool = False

    model_config = ConfigDict(
        env_file=dotenv_path,
        env_file_encoding="utf-8",
        extra='ignore'
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        # Force-load Gemini API key from .env file, override system environment
        try:
            from dotenv import dotenv_values
            env_values = dotenv_values(dotenv_path)
            if 'GEMINI_API_KEY' in env_values:
                self.GEMINI_API_KEY = env_values['GEMINI_API_KEY']
                logger.debug(f"Forcefully loaded GEMINI_API_KEY from .env file")
        except Exception as e:
            logger.error(f"Error loading GEMINI_API_KEY from .env file: {e}", exc_info=True)


# Remove lru_cache temporarily to test if caching causes issues
def get_settings() -> Settings:
    """Return settings instance. Settings are loaded fresh each time this is called."""
    logger.info("Loading application settings...")
    try:
        settings = Settings()
        logger.info("Application settings loaded successfully.")
        # Optional: Log some settings for verification (be careful with sensitive data)
        logger.debug(f"DB Server: {settings.DB_SERVER}, Gemini Model: {settings.GEMINI_MODEL}")
        logger.debug(f"Log Level: {settings.LOG_LEVEL}, Log Full Gemini IO: {settings.LOG_FULL_GEMINI_IO}")
        return settings
    except Exception as e:
        logger.exception(f"Failed to load application settings: {e}")
        raise RuntimeError(f"Could not load settings: {e}")
