from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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

settings = Setting()