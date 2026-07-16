"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by command-line tools and future API services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CREATIVEBENCH_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    data_dir: Path = Path("data")
    taxonomy_path: Path = Path("data/taxonomy.json")
    examples_path: Path = Path("data/examples/prompts.jsonl")
    import_output_path: Path = Path("data/processed/imported_prompts.jsonl")
    dedup_output_path: Path = Path("data/processed/deduplicated_prompts.jsonl")
    dedup_report_path: Path = Path("data/processed/duplicate_report.jsonl")
    min_prompt_length: int = Field(default=5, ge=1)
    max_prompt_length: int = Field(default=10_000, ge=1)
    near_duplicate_max_distance: int = Field(default=8, ge=0, le=64)
    semantic_duplicate_threshold: float = Field(default=0.80, ge=0, le=1)
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    low_confidence_threshold: float = Field(default=0.7, ge=0, le=1)


def get_settings() -> Settings:
    """Create settings from defaults, .env and process environment variables."""

    return Settings()
