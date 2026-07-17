"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    database_url: str = "sqlite:///data/creativebench.db"
    knowledge_documents_path: Path = Path("data/processed/knowledge_documents.jsonl")
    vector_store_path: Path = Path("data/vector_store")
    knowledge_collection: str = "creativebench_knowledge"
    knowledge_top_k: int = Field(default=5, ge=1, le=50)
    rag_label_top_k: int = Field(default=2, ge=1, le=10)
    rag_example_top_k: int = Field(default=4, ge=1, le=20)
    glm_api_key: SecretStr | None = None
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    glm_model: str = "glm-4-flash-250414"
    glm_timeout_seconds: float = Field(default=60, gt=0)
    glm_max_attempts: int = Field(default=3, ge=1, le=10)
    glm_retry_delay_seconds: float = Field(default=1, ge=0, le=60)
    evaluation_cases_path: Path = Path("data/evaluation/cases.jsonl")
    evaluation_predictions_path: Path = Path("data/evaluation/predictions.jsonl")
    evaluation_report_path: Path = Path("reports/evaluation.json")
    security_benchmark_path: Path = Path("data/evaluation/security_cases.jsonl")
    min_prompt_length: int = Field(default=5, ge=1)
    max_prompt_length: int = Field(default=10_000, ge=1)
    near_duplicate_max_distance: int = Field(default=8, ge=0, le=64)
    semantic_duplicate_threshold: float = Field(default=0.80, ge=0, le=1)
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_query_instruction: str = "为这个句子生成表示以用于检索相关文章："
    low_confidence_threshold: float = Field(default=0.7, ge=0, le=1)


def get_settings() -> Settings:
    """Create settings from defaults, .env and process environment variables."""

    return Settings()
