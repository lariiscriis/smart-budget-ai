from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

BACKEND_DIR = Path(__file__).resolve().parent.parent

class Setting(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_enconding="utf-8",
    )

    db_host: str
    db_port: int = Field(ge=1, le=65535)
    db_name: str
    db_user: str
    db_password: SecretStr

    ai_mode: Literal["mock", "gemini"] = "mock"
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr | None = None

    n8n_webhook_url: str = (
        "http://localhost:5678/webhook/smartbudget-summary"
    )

settings = Setting()

