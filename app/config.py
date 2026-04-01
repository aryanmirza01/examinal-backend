"""
Central settings — Full NVIDIA stack configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "Examinal"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    SECRET_KEY: str = "CHANGE-ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "sqlite:///./examinal.db"

    # ── NVIDIA NIM ──
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # ── LLM ──
    LLM_PROVIDER: str = "nvidia"
    NVIDIA_LLM_MODEL: str = "nvidia/nemotron-3-nano-30b-a3b"
    LLM_TEMPERATURE: float = 0.4
    LLM_MAX_TOKENS: int = 8192

    # ── Fallback LLM ──
    FALLBACK_LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # ── Embedding ──
    EMBEDDING_PROVIDER: str = "nvidia_api"
    NVIDIA_EMBED_MODEL: str = "nvidia/llama-3.2-nv-embedqa-1b-v2"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── Reranking ──
    USE_RERANKER: bool = True
    NVIDIA_RERANK_MODEL: str = "nvidia/llama-nemotron-rerank-1b-v2"

    # ── Retrieval ──
    RETRIEVAL_TOP_K: int = 25
    RERANK_TOP_K: int = 6
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 150

    # ── Grading ──
    GRADING_MODE: str = "multi_pass"
    GRADING_CONFIDENCE_THRESHOLD: float = 0.7
    ENABLE_RUBRIC_GRADING: bool = True

    MAIL_USERNAME: str = "aryanmirza112233@gmail.com"
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "aryanmirza112233@gmail.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_USE_TLS: bool = True
    MAIL_USE_SSL: bool = False

    # ── Paths ──
    UPLOAD_DIR: str = "uploads"
    VECTOR_STORE_DIR: str = "vector_store_data"
    MAX_UPLOAD_SIZE_MB: int = 50


settings = Settings()