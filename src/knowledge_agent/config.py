"""Single configuration boundary: CLI overrides > environment > .env > defaults."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    mode: Literal["real", "mock"] = "real"
    deepseek_api_key: SecretStr | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    model_name: str = Field(default="deepseek-flash", min_length=1)
    base_url: str = "https://api.deepseek.com"
    # This initial integration deliberately has no thinking-mode switch.
    thinking: Literal[False] = False
    corpus_path: Path = Path("data/smoke/manifest.json")
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
    max_tool_chars: int = Field(default=12_000, ge=1)

    @property
    def has_api_key(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_api_key.get_secret_value().strip())

    def public_config(self) -> dict:
        """Never serialize credentials, including their masked value."""
        return {
            **self.model_dump(mode="json", exclude={"deepseek_api_key"}),
            "api_key_present": self.has_api_key,
            "stage": "integration_smoke",
            "retrieval": "smoke_fixture",
        }


def load_settings(**overrides: object) -> Settings:
    return Settings(**{key: value for key, value in overrides.items() if value is not None})
