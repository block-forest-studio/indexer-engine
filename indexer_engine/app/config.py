"""Config file."""
from urllib.parse import quote_plus
from uuid import UUID

from pydantic import AnyHttpUrl, EmailStr, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # PROJECT
    project_name: str = Field(..., alias="PROJECT_NAME")

    # DATABASE
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(..., alias="POSTGRES_PASSWORD")
    postgres_server: str = Field(..., alias="POSTGRES_SERVER")
    postgres_port: int = Field(..., alias="POSTGRES_PORT")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    database_url: str | None = None
    sync_database_url: str | None = None

    @model_validator(mode="after")
    def assemble_db_urls(self) -> "Settings":
        if not self.database_url:
            user = quote_plus(self.postgres_user)
            password = quote_plus(self.postgres_password.get_secret_value())
            host = self.postgres_server
            port = self.postgres_port
            db = self.postgres_db

            self.database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

        if not self.sync_database_url:
            user = quote_plus(self.postgres_user)
            password = quote_plus(self.postgres_password.get_secret_value())
            host = self.postgres_server
            port = self.postgres_port
            db = self.postgres_db

            self.sync_database_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"

        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings: Settings = Settings()
