"""Camada de acesso ao LLM e aos embeddings (provider-agnostic, P8).

Trocar de provedor é mudar `LLM_PROVIDER`/`LLM_MODEL` no ambiente. O default é Gemini.
A chave é exportada para o ambiente aqui para que os SDKs subjacentes a encontrem.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model

from src.config import settings

# Os SDKs do Google leem GOOGLE_API_KEY do ambiente; espelhamos a partir do .env.
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)


@lru_cache(maxsize=1)
def get_chat() -> Any:
    """Modelo de chat configurado (cacheado)."""
    return init_chat_model(
        settings.llm_model, model_provider=settings.llm_provider, temperature=0.2
    )


@lru_cache(maxsize=1)
def get_embeddings() -> Any:
    """Modelo de embeddings do mesmo provedor (para o RAG efêmero)."""
    if settings.llm_provider == "google_genai":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001", google_api_key=settings.google_api_key
        )
    if settings.llm_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model="text-embedding-3-small")
    raise ValueError(f"Embeddings não configurados para o provedor {settings.llm_provider!r}")
