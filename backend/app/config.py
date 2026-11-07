from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[1] / ".env", Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "production", "testing"] = "development"
    LOG_LEVEL: str = "INFO"

    # MongoDB Atlas
    MONGODB_ATLAS_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE_NAME: str = "nevertwice_memory"
    MONGODB_VECTOR_INDEX: str = "skill_rules_vector_index"
    MONGODB_AI_ENDPOINT: str = "ai.mongodb.com"
    MONGODB_AI_API_KEY: str = ""

    # Google DeepMind Judge & Embeddings
    GOOGLE_API_KEY: str = ""
    GEMINI_JUDGE_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # Subquadratic Context Reconstructor
    SUBQUADRATIC_API_KEY: str = ""
    SUBQUADRATIC_BASE_URL: str = "https://api.subquadratic.ai/v1"
    SUBQ_TIMEOUT_SECONDS: float = 3.5

    # Meta Model API Swarm
    META_API_KEY: str = ""
    META_BASE_URL: str = "https://api.meta.ai/v1"
    META_TIMEOUT_SECONDS: float = 8.0

    # Pytest Sandbox
    SANDBOX_TIMEOUT_SECONDS: float = 5.0

    # Fetch.ai uAgents Protocol
    FETCHAI_AGENT_NAME: str = "nevertwice_pipeline_agent"
    FETCHAI_AGENT_SEED: str = "nevertwice_default_seed_phrase"
    FETCHAI_AGENT_PORT: int = 8001
    FETCHAI_AGENT_ENDPOINT: str = ""
    FETCHAI_MAILBOX_KEY: str = ""
    AGENTVERSE_API_KEY: str = ""


settings = Settings()
