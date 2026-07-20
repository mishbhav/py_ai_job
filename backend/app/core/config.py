"""
Centralized application configuration.

All tunables live here so routes/services never hardcode magic numbers
or read os.environ directly. Values are overridable via a .env file
or real environment variables (useful for Codespaces secrets).
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Job Market Fit Analyzer"
    ENV: str = "development"

    # --- CORS ---
    # In Codespaces the frontend is served from a forwarded *.app.github.dev URL,
    # which is NOT known ahead of time, so we allow overriding via env var.
    CORS_ALLOW_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    CORS_ALLOW_ORIGIN_REGEX: str = r"https://.*\.app\.github\.dev"

    # --- Scraping ---
    NAUKRI_BASE_URL: str = "https://www.naukri.com"
    SCRAPE_MAX_JOBS: int = 40
    SCRAPE_TIMEOUT_MS: int = 30_000
    SCRAPE_HEADLESS: bool = True
    SCRAPE_MIN_DELAY_S: float = 1.5  # politeness delay between page interactions
    SCRAPE_MAX_RETRIES: int = 2

    # --- NLP ---
    TOP_KEYWORDS_COUNT: int = 10
    TFIDF_MAX_FEATURES: int = 5000

    # --- LLM (Anthropic) ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    LLM_MAX_TOKENS: int = 1500

    # --- Uploads ---
    MAX_CV_SIZE_MB: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
