"""Estado tipado do grafo do agente (contrato explícito entre os nós, P7)."""
from __future__ import annotations

from typing import Any, TypedDict


class ReportState(TypedDict, total=False):
    report_id: str
    data_ref: Any
    metrics: dict
    search_query: str
    news: list[dict]
    commentary: dict
    sources: list[str]
