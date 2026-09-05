# api/core/config.py
# Application settings loaded from environment variables (.env)

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "S.P.A.R.K."
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://spark_user:spark_password@postgres:5432/spark_db"
    POSTGRES_DB: str = "spark_db"
    POSTGRES_USER: str = "spark_user"
    POSTGRES_PASSWORD: str = "spark_password"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Security & Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
