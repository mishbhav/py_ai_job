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

    # Inside your Settings class in app/core/config.py
    ADZUNA_APP_ID: str = "6af77c45"
    ADZUNA_APP_KEY: str ="381ed49f7882cd2bdce0ab31ff1805ae"


    # --- LLM provider selection ---
    # "huggingface_api"  -> free Hugging Face serverless Inference API (needs a free HF token, no billing)
    # "local_transformers" -> fully offline open-source model, no token, no internet needed at inference time
    # "anthropic"        -> paid, kept for anyone who wants higher-quality output
    LLM_PROVIDER: str = "huggingface_api"
    LLM_MAX_TOKENS: int = 1500

    # --- Hugging Face free Inference API ---
    # Create a free token at https://huggingface.co/settings/tokens (read scope is enough).
    # Which instruct models are "warm" on the free tier changes over time — check
    # https://huggingface.co/models?pipeline_tag=text-generation&inference_provider=all
    # and swap HF_INFERENCE_MODEL if this one is unavailable.
    HF_API_TOKEN: str = ""
    HF_INFERENCE_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"

    # --- Fully local/offline model (transformers, runs on CPU) ---
    # Small enough to run without a GPU in a Codespaces container. Swap for a
    # bigger checkpoint if your Codespace has more RAM/CPU to spare.
    LOCAL_MODEL_ID: str = "Qwen/Qwen2.5-1.5B-Instruct"

    # --- Anthropic (optional, paid) ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # --- Uploads ---
    MAX_CV_SIZE_MB: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
