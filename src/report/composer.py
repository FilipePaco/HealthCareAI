"""Composição do relatório: comentário por métrica com grounding obrigatório (R5.2–R5.6).

O LLM produz saída estruturada (Pydantic). Em seguida o grounding é *forçado* em código:
qualquer fonte citada que não esteja entre as notícias fornecidas é removida (R5.4) — o modelo
não consegue "inventar" uma fonte que sobreviva à verificação.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agent.llm import get_chat
from src.agent.prompts import (
    SYSTEM_COMPOSER,
    SYSTEM_QUERY,
    composer_user_prompt,
    scenario_text,
)
from src.governance.usage import UsageTracker


class MetricComment(BaseModel):
    metric: str = Field(description="nome da métrica")
    explanation: str = Field(description="explicação contextual ancorada no valor e nas notícias")
    sources: list[str] = Field(default_factory=list, description="URLs das notícias citadas")


class ReportCommentary(BaseModel):
    per_metric: list[MetricComment] = Field(default_factory=list)
    synthesis: str = ""
    sources: list[str] = Field(default_factory=list)


def enforce_grounding(commentary: ReportCommentary, allowed_urls: set[str]) -> ReportCommentary:
    """Mantém apenas fontes que estão entre as notícias recuperadas (R5.4)."""

    def keep(urls: list[str]) -> list[str]:
        return [u for u in urls if u in allowed_urls]

    commentary.per_metric = [
        MetricComment(metric=c.metric, explanation=c.explanation, sources=keep(c.sources))
        for c in commentary.per_metric
    ]
    commentary.sources = keep(commentary.sources)
    return commentary


def formulate_query(metrics: dict, usage: UsageTracker | None = None) -> str:
    """Formula os termos de busca a partir do cenário (fallback determinístico do nó de notícias)."""
    resp = get_chat().invoke(
        [SystemMessage(SYSTEM_QUERY), HumanMessage(scenario_text(metrics))]
    )
    if usage is not None:
        usage.record_llm(resp)
    raw = (resp.content or "").strip().strip('"')
    query = raw.splitlines()[0].strip() if raw else ""
    return query[:200] or "SRAG síndrome respiratória aguda grave notícias Brasil"


def compose_commentary(
    metrics: dict, news: list[dict], usage: UsageTracker | None = None
) -> ReportCommentary:
    """Gera o comentário por métrica + síntese, com grounding forçado.

    Usa `include_raw=True` para capturar o `usage_metadata` da resposta (tokens) sem perder a
    saída estruturada (P9).
    """
    allowed = {n["url"] for n in news if n.get("url")}
    chat = get_chat().with_structured_output(ReportCommentary, include_raw=True)
    result = chat.invoke(
        [SystemMessage(SYSTEM_COMPOSER), HumanMessage(composer_user_prompt(metrics, news))]
    )
    if usage is not None and result.get("raw") is not None:
        usage.record_llm(result["raw"])
    parsed = result.get("parsed")
    if parsed is None:  # falha de parsing -> trata como LLM indisponível (nó compose degrada)
        raise ValueError(f"saída estruturada inválida: {result.get('parsing_error')}")
    return enforce_grounding(parsed, allowed)
