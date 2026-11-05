"""Load test configuration without reading .env or connecting to real services."""
import os
from unittest.mock import patch

from pydantic_settings import DotEnvSettingsSource

# Some existing unit tests import the worker/database at collection time. Load
# configuration first under isolation so those imports never consult local .env.
with patch.object(DotEnvSettingsSource, "_read_env_files", return_value={}), patch.dict(
    os.environ,
    {
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "3306",
        "DB_NAME": "aurora_test_unused",
        "DB_USER": "test_unused",
        "DB_PASSWORD": "test_unused",
        "AI_MODE": "mock",
        "AUTH_COOKIE_SECURE": "false",
        "GEMINI_API_KEY": "test_unused",
    },
):
    from app.config import settings  # noqa: F401
