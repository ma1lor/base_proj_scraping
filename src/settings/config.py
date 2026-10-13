from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    project_name: str = Field(
        min_length=1,
        max_length=63,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    postgres_user: str = Field(default="postgres", min_length=1)
    postgres_password: SecretStr = Field(min_length=1)
    postgres_host: str = Field(default="localhost", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    logs_dir: Path = PROJECT_DIR / "src" / "logs"

    @property
    def postgres_db(self) -> str:
        return self.project_name
