"""Configuração centralizada (P7): toda variável de ambiente passa por aqui.

Nada de `os.getenv` espalhado pelo código; limiares e janelas vêm daqui.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (provider-agnostic, P8)
    llm_provider: str = "google_genai"
    llm_model: str = "gemini-2.5-flash"
    google_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    tavily_api_key: str | None = None

    # Banco
    database_url: str = "postgresql+psycopg2://srag:srag@localhost:5432/srag"

    # Segurança da API (P5)
    api_key: str | None = None
    cors_origins: str = "http://localhost:8501"
    rate_limit: str = "30/minute"

    # Parâmetros das métricas (P7 — sem números mágicos)
    report_increase_window_days: int = 14
    news_recency_days: int = 30

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
