"""Guardrails da fronteira HTTP (P5): API key, rate limiting e CORS.

Sem autenticação de usuários (fora de escopo, ADR-10) — apenas proteção mínima da API.
"""
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Dependência: rejeita request sem API key válida (R7.4)."""
    if not settings.api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="API key inválida ou ausente")


def configure_cors(app: FastAPI) -> None:
    """Aplica CORS restrito às origens configuradas (R7.6)."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
