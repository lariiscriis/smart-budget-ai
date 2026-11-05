import re
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[a-z0-9][a-z0-9._%+\-]*@[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+", value):
        raise ValueError("Informe um email válido.")
    local, domain = value.split("@")
    if len(local) > 64 or ".." in local or local.endswith(".") or any(len(label) > 63 for label in domain.split(".")):
        raise ValueError("Informe um email válido.")
    return value


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value: str) -> str:
        return normalize_email(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    is_demo: bool


class SessionRead(BaseModel):
    user: UserRead
    workspace: WorkspaceRead
    csrf_token: str
