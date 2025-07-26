import os
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

from utils.logger import initialize_logger
from utils.request_context import RequestContext


class LLMSettings(BaseSettings):

    GOOGLE_API_KEY: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    @model_validator(mode="after")
    def check_at_least_one_key(self):
        if not (
            self.GOOGLE_API_KEY or self.AZURE_OPENAI_API_KEY or self.OPENAI_API_KEY
        ):
            raise ValueError(
                "At least one API key must be set. Set GOOGLE_API_KEY, AZURE_OPENAI_API_KEY, or OPENAI_API_KEY."
            )
        return self


class AppEnvSettings(BaseSettings):

    APP_ENVIRONMENT: Literal["development", "staging", "production"] = "development"


class CelerySettings(BaseSettings):

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    CELERY_FASTAPI_HOST: str

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def validate_celery_broker_url(cls, value: str):
        if not value.startswith("redis://"):
            raise ValueError("CELERY_BROKER_URL must start with 'redis://'")
        return value

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def validate_celery_result_backend(cls, value: str):
        if not value.startswith("db+postgresql+psycopg://"):
            raise ValueError(
                "CELERY_RESULT_BACKEND must start with 'db+postgresql+psycopg://'"
            )
        return value


class DatabaseSettings(BaseSettings):

    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, value: str):
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must start with 'postgresql+psycopg://'")
        return value


class Settings(
    DatabaseSettings, CelerySettings, AppEnvSettings, LLMSettings, case_sensitive=True
):
    """
    Settings class to hold application configuration.
    """

    class Config:
        env_file = (
            ".env"
            if os.getenv("ENV_POSTFIX") is None
            else f".env.{os.getenv('ENV_POSTFIX')}"
        )  # Use environment variable to determine the env file. For example, if ENV_POSTFIX=staging, then the env file will be .env.staging
        env_file_encoding = "utf-8"
        extra = "ignore"


env = Settings()  # pyright: ignore[reportCallIssue]


# Initialize request context for logging
request_context = RequestContext()
logger = initialize_logger(
    context=request_context,
    level="INFO" if env.APP_ENVIRONMENT != "production" else "WARNING",
)
# Set up project root directory.
PROJECT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

logger.warning(f"Application environment: {env.APP_ENVIRONMENT}")
logger.warning(f"Project root directory: {PROJECT_ROOT_DIR}")
