"""Single configuration boundary: CLI overrides > environment > .env > defaults."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    mode: Literal["real", "mock"] = "real"
    retrieval_mode: Literal["bm25", "vector", "hybrid"] | None = None
    rrf_k: int = Field(default=60, ge=1)
    mock_scenario: Literal["normal", "conflict", "missing", "tool_failure", "recovery", "budget"] | None = None
    deepseek_api_key: SecretStr | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    model_name: str = Field(default="deepseek-flash", min_length=1)
    base_url: str = "https://api.deepseek.com"
    # Thinking mode is disabled for all model requests.
    thinking: Literal[False] = False
    corpus_path: Path = Path("data/smoke/manifest.json")
    prepared_path: Path | None = None
    output_dir: Path = Path("runtime/runs")
    max_model_turns: int = Field(default=10, ge=1)
    max_http_attempts: int = Field(default=20, ge=1)
    max_tool_calls: int = Field(default=16, ge=1)
    output_retries: int = Field(default=2, ge=0, le=2)
    transport_retries: int = Field(default=1, ge=0, le=1)
    model_timeout: float = Field(default=30, gt=0)
    tool_timeout: float = Field(default=10, gt=0)
    turn_timeout: float = Field(default=120, gt=0)
    max_input_chars: int = Field(default=100_000, ge=1)
    model_context_tokens: int = Field(default=65_536, ge=1)
    model_output_tokens: int = Field(default=2_048, ge=1)
    max_tool_chars: int = Field(default=12_000, ge=1)
    # Shared retrieval configuration; prepared_path selects indexed tool integration.
    tokenizer_path: Path = Path("runtime/models/bge-small-zh-v1.5-tokenizer/tokenizer.json")
    retrieval_cache_dir: Path = Path("runtime/cache/retrieval")
    chunk_target_tokens: int = Field(default=320, ge=32, le=480)
    chunk_max_tokens: int = Field(default=480, ge=32, le=480)
    chunk_overlap_tokens: int = Field(default=48, ge=0)
    bm25_k1: float = Field(default=1.5, gt=0)
    bm25_b: float = Field(default=0.75, ge=0, le=1)
    bm25_epsilon: float = Field(default=0.25, ge=0)
    search_cursor_capacity: int = Field(default=256, ge=1)
    read_cursor_capacity: int = Field(default=256, ge=1)
    # Local vector backend. Model identity is pinned in retrieval/model_assets.py.
    embedding_model_path: Path = Path("runtime/models/bge-small-zh-v1.5")
    embedding_timeout: float = Field(default=10, gt=0)
    embedding_startup_timeout: float = Field(default=120, gt=0)
    embedding_prepare_timeout: float = Field(default=120, gt=0)
    embedding_batch_size: int = Field(default=16, ge=1, le=128)
    embedding_threads: int = Field(default=2, ge=1, le=32)
    embedding_stop_timeout: float = Field(default=1, gt=0, le=5)

    @model_validator(mode="after")
    def consistent_chunk_limits(self) -> "Settings":
        if self.mode == "mock" and self.retrieval_mode not in {None, "bm25"}:
            raise PydanticCustomError(
                "mock_retrieval_mode",
                "Mock 仅支持 BM25；请使用 --retrieval bm25 或移除 KA_RETRIEVAL_MODE 的非 BM25 配置。",
            )
        if self.mode == "real" and self.mock_scenario is not None:
            raise ValueError("mock_scenario is only available in explicit mock mode")
        if self.model_output_tokens >= self.model_context_tokens:
            raise ValueError("model output reserve must be smaller than context capacity")
        if self.chunk_target_tokens > self.chunk_max_tokens:
            raise ValueError("chunk target must not exceed the hard limit")
        if self.chunk_overlap_tokens >= self.chunk_target_tokens // 2:
            raise ValueError("chunk overlap must be less than half the target")
        return self

    @property
    def selected_retrieval(self) -> str:
        return self.retrieval_mode or ("bm25" if self.mode == "mock" else "hybrid")

    @property
    def has_api_key(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_api_key.get_secret_value().strip())

    def public_config(self) -> dict:
        """Never serialize credentials, including their masked value."""
        return {
            **self.model_dump(mode="json", exclude={"deepseek_api_key"}),
            "api_key_present": self.has_api_key,
            "stage": "tool_integration" if self.prepared_path else "integration_smoke",
            "retrieval": self.selected_retrieval if self.prepared_path else "smoke_fixture",
        }


def load_settings(**overrides: object) -> Settings:
    return Settings(**{key: value for key, value in overrides.items() if value is not None})
