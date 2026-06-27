"""Aplicação FastAPI (API-first). Monta segurança (P5) e as rotas."""
from __future__ import annotations

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.routes import router
from src.api.security import configure_cors, limiter


def create_app() -> FastAPI:
    app = FastAPI(title="SRAG Report Agent", version="0.1.0")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)  # aplica RATE_LIMIT globalmente (R7.5)
    configure_cors(app)
    app.include_router(router)
    return app


app = create_app()
