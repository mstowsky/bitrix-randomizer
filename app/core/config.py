"""Application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Bitrix Randomizer"
    app_env: str = "development"
    debug: bool = False
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bitrix_randomizer"


settings = Settings()
