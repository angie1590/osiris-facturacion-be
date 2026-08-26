from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "production", "test"] = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://osiris:osiris_dev_pass@localhost:5432/osiris_facturacion"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Facturación Electrónica (fe-ec)
    FEEC_P12_PATH: str = "conf/firma.p12"
    FEEC_P12_PASSWORD: str = ""
    FEEC_XSD_PATH: str = "conf/sri_docs/factura_V1_1.xsd"
    FEEC_AMBIENTE: Literal["pruebas", "produccion"] = "pruebas"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    APP_TIMEZONE: str = "America/Guayaquil"


settings = Settings()
