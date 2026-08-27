"""Camada 2 de observabilidade: tracing do agente no Langfuse (ADR-13, R11.x).

Este é o **único** módulo que conhece o Langfuse (R11.8): trocar de backend de tracing — ou
removê-lo — é mexer aqui e em lugar nenhum mais.

Contrato de degradação (R11.3): se o tracing estiver desligado, sem credenciais, com o SDK ausente
ou com o coletor fora do ar, `runnable_config()` devolve `{}` e a aplicação se comporta exatamente
como se o tracing não existisse. **Tracing nunca é caminho crítico** — a camada 1 (`audit_log`)
segue registrando tudo de qualquer forma.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

# O `report_id` é um uuid4().hex — 32 caracteres hex, exatamente o formato de trace id do
# OpenTelemetry, que o Langfuse adota. Isso deixa report_id e trace_id serem o mesmo valor (R11.2).
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def tracing_active() -> bool:
    """True apenas se o tracing foi habilitado E há credenciais para usar."""
    return bool(
        settings.tracing_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def _export_credentials() -> None:
    """Espelha as credenciais da config para o ambiente, onde o SDK as procura.

    Mesmo padrão já usado em `src/agent/llm.py` para as chaves de LLM: a config continua sendo a
    única fonte (P7). `LANGFUSE_HOST` e `LANGFUSE_BASE_URL` são ambos exportados porque o nome da
    variável mudou entre versões maiores do SDK.
    """
    for name, value in (
        ("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key),
        ("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key),
        ("LANGFUSE_HOST", settings.langfuse_host),
        ("LANGFUSE_BASE_URL", settings.langfuse_host),
        ("LANGFUSE_SAMPLE_RATE", str(settings.langfuse_sample_rate)),
    ):
        if value:
            os.environ.setdefault(name, str(value))


def _handler(report_id: str) -> Any | None:
    """Instancia o CallbackHandler do Langfuse, ou None se não for possível."""
    from langfuse.langchain import CallbackHandler  # import tardio: dependência opcional

    if _TRACE_ID_RE.match(report_id):
        try:
            return CallbackHandler(trace_context={"trace_id": report_id})
        except TypeError:
            # SDK sem suporte a `trace_context`; o vínculo com o report_id fica por
            # `langfuse_session_id` nos metadados, que toda versão aceita.
            logger.debug("CallbackHandler sem trace_context; usando session_id")
    return CallbackHandler()


def get_callbacks(report_id: str) -> list[Any]:
    """Callbacks de tracing para esta geração de relatório. Lista vazia = tracing desligado."""
    if not tracing_active():
        return []
    try:
        _export_credentials()
        handler = _handler(report_id)
        return [handler] if handler is not None else []
    except Exception as exc:  # noqa: BLE001 - SDK ausente/incompatível/sem rede: segue sem tracing
        logger.warning("tracing indisponível, seguindo sem ele: %s", exc)
        return []


def trace_metadata(report_id: str) -> dict:
    """Atributos que o Langfuse lê dos metadados do LangChain para agrupar e filtrar traces."""
    return {
        "langfuse_session_id": report_id,
        "langfuse_tags": [
            "srag-report",
            f"env:{settings.environment}",
            f"model:{settings.llm_model}",
        ],
    }


def runnable_config(report_id: str) -> dict:
    """Config do LangChain a propagar por todo o grafo. `{}` quando o tracing está desligado.

    É passada explicitamente de nó em nó (em vez de confiar na propagação implícita por
    contextvar), para que o trace saia completo independentemente da versão do LangChain.
    """
    callbacks = get_callbacks(report_id)
    if not callbacks:
        return {}
    return {"callbacks": callbacks, "metadata": trace_metadata(report_id)}


def flush() -> None:
    """Despacha traces pendentes ao fim da requisição. Falha aqui nunca é erro (R11.3)."""
    if not tracing_active():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as exc:  # noqa: BLE001 - despacho é best-effort
        logger.debug("flush de tracing falhou (ignorado): %s", exc)
