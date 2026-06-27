"""Observabilidade de uso e custo dos recursos pagos (P9, R10.x, ADR-12).

Acompanha, por relatório, o consumo de **LLM** (chamadas + tokens de entrada/saída, lidos do
`usage_metadata` de cada resposta LangChain) e de **busca Tavily** (nº de buscas), e estima o
custo em USD a partir de tarifas configuráveis (`src/config.py`). É **estimativa**, não fatura.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.config import settings


def _usage_metadata(message: Any) -> dict:
    """Extrai o `usage_metadata` de uma resposta do LangChain, tolerante a formatos."""
    meta = getattr(message, "usage_metadata", None)
    if not meta and isinstance(message, dict):
        meta = message.get("usage_metadata")
    return meta or {}


@dataclass
class UsageTracker:
    """Acumula o consumo de LLM e de busca de uma geração de relatório."""

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tavily_searches: int = 0

    def record_llm(self, message: Any) -> None:
        """Contabiliza uma chamada de LLM a partir da resposta (AIMessage com usage_metadata)."""
        self.llm_calls += 1
        meta = _usage_metadata(message)
        self.input_tokens += int(meta.get("input_tokens", 0) or 0)
        self.output_tokens += int(meta.get("output_tokens", 0) or 0)

    def record_search(self, n: int = 1) -> None:
        """Contabiliza buscas de notícias (Tavily)."""
        self.tavily_searches += int(n)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def estimated_cost_usd(self) -> float:
        """Custo aproximado por tarifas configuráveis (P7). Estimativa, não fatura."""
        cost = (
            self.input_tokens / 1_000_000 * settings.llm_input_cost_per_1m
            + self.output_tokens / 1_000_000 * settings.llm_output_cost_per_1m
            + self.tavily_searches * settings.tavily_cost_per_search
        )
        return round(cost, 6)

    def as_dict(self) -> dict:
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "tavily_searches": self.tavily_searches,
            "estimated_cost_usd": self.estimated_cost_usd(),
            "estimate": True,
        }
