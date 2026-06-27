"""Tool de notícias via Tavily (busca desenhada para agentes): retorna trecho + fonte + data.

Respeita a janela de recência (R4.3) e, se a busca falhar/ficar sem chave, devolve lista
vazia para o fallback do agente (R4.4).
"""
from __future__ import annotations

from dataclasses import dataclass

from src.config import settings


@dataclass
class Article:
    title: str
    url: str
    date: str | None
    content: str


def search_news(
    query: str, max_results: int = 6, days: int | None = None, topic: str = "general"
) -> list[Article]:
    """Busca notícias recentes. Lista vazia se não houver chave ou em caso de falha (R4.4).

    `topic="general"` dá melhor relevância para o tema de saúde do que o índice "news"
    (que tende a casar termos genéricos como "grave"). A janela de recência só se aplica a "news".
    """
    if not settings.tavily_api_key or "your-" in settings.tavily_api_key:
        return []
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        kwargs: dict = {"query": query, "max_results": max_results, "topic": topic}
        if topic == "news":
            kwargs["days"] = days or settings.news_recency_days
        resp = client.search(**kwargs)
    except Exception:  # noqa: BLE001 - qualquer falha de rede/quota cai no fallback
        return []

    return [
        Article(
            title=item.get("title", ""),
            url=item.get("url", ""),
            date=item.get("published_date"),
            content=item.get("content", ""),
        )
        for item in resp.get("results", [])
    ]
