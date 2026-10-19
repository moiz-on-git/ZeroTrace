"""
ZeroTrace Data Plane — central configuration.
All settings read from environment variables (ZT_ prefix).
Never hard-code secrets.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ZT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Service ──────────────────────────────────────────────────────────────
    env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    service_key: str = Field(default="changeme-service-key")
    data_plane_port: int = 8002

    # ── Postgres ─────────────────────────────────────────────────────────────
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "ztuser"
    pg_password: str = "changeme"
    pg_db_app: str = "zt_app"
    pg_db_rag: str = "zt_rag"
    pg_db_catalog: str = "zt_catalog"

    @property
    def pg_dsn_app(self) -> str:
        # Use asyncpg for async SQLAlchemy (works on Windows ProactorEventLoop)
        return (
            f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db_app}"
        )

    @property
    def pg_dsn_rag(self) -> str:
        return (
            f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db_rag}"
        )

    @property
    def pg_dsn_catalog(self) -> str:
        # Sync driver for Iceberg JDBC catalog
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db_catalog}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_cache_db: int = 0   # semantic cache
    redis_queue_db: int = 1   # event bus / ARQ

    # ── S3 / MinIO ───────────────────────────────────────────────────────────
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "kaveri-finserv-lake"
    s3_region: str = "ap-south-1"
    s3_versioning_enabled: bool = True

    # ── Iceberg ──────────────────────────────────────────────────────────────
    iceberg_catalog_type: Literal["jdbc", "rest"] = "jdbc"
    iceberg_catalog_jdbc_uri: str = (
        "postgresql+psycopg2://ztuser:changeme@localhost:5432/zt_catalog"
    )
    iceberg_catalog_rest_uri: str = "http://localhost:8181"
    iceberg_warehouse: str = "s3a://kaveri-finserv-lake/warehouse"

    # ── Spark ────────────────────────────────────────────────────────────────
    spark_driver_memory: str = "4g"
    spark_executor_memory: str = "2g"
    spark_local_dirs: str = "/tmp/spark-local"

    # ── Embeddings ───────────────────────────────────────────────────────────
    embed_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embed_model_path: str = "/app/models/embed"

    # ── LLM (optional) ───────────────────────────────────────────────────────
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # ── Crypto shred ─────────────────────────────────────────────────────────
    enable_crypto_shred: bool = False
    master_key: str = "changeme-32-byte-master-key-here!"

    # ── Demo ─────────────────────────────────────────────────────────────────
    demo_auto_approve: bool = False
    demo_ghost_miss: bool = False   # when True: first audit pass skips semantic sweep

    # ── Seed ─────────────────────────────────────────────────────────────────
    seed_profile: Literal["small", "showtime"] = "small"
    seed_random_seed: int = 42

    @field_validator("log_level")
    @classmethod
    def upper_log_level(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
