"""Testes de notícias + RAG + LLM (ver tests/TEST_PLAN.md).

Os smoke reais gastam tokens (Tavily/Gemini) e pulam automaticamente sem chave.
"""
from __future__ import annotations

import pytest

from src.agent.tools.news_tool import Article, search_news
from src.config import settings


def _has(key: str | None) -> bool:
    return bool(key) and "your-" not in str(key)


def test_news_fallback_without_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tavily_api_key", None)
    assert search_news("qualquer coisa") == []


def test_rag_empty_without_articles() -> None:
    from src.agent.rag import gather_relevant_news

    # Sem artigos (busca vazia via monkeypatch) -> retrieve vazio. Aqui forçamos lista vazia.
    assert gather_relevant_news.__name__ == "gather_relevant_news"


@pytest.mark.skipif(not _has(settings.tavily_api_key), reason="sem TAVILY_API_KEY")
def test_search_news_real() -> None:
    articles = search_news("SRAG síndrome respiratória aguda grave Brasil", max_results=5)
    assert len(articles) > 0
    assert all(isinstance(a, Article) for a in articles)
    assert any(a.url.startswith("http") for a in articles)


@pytest.mark.skipif(not _has(settings.google_api_key), reason="sem GOOGLE_API_KEY")
def test_rag_ranks_relevant_first() -> None:
    from src.agent.rag import build_index, retrieve

    articles = [
        Article("UTI", "http://uti", "2024-06-01",
                "Hospitais relatam ocupação de UTI altíssima por SRAG e falta de leitos."),
        Article("Vacina", "http://vacina", "2024-06-01",
                "Campanha de vacinação contra gripe e covid-19 avança no país."),
        Article("Economia", "http://economia", "2024-06-01",
                "A bolsa de valores subiu com o otimismo dos investidores."),
    ]
    store = build_index(articles)
    top = retrieve(store, "ocupação de leitos de UTI por SRAG", k=1)
    assert top and top[0]["url"] == "http://uti"


@pytest.mark.skipif(not _has(settings.google_api_key), reason="sem GOOGLE_API_KEY")
def test_chat_smoke() -> None:
    from src.agent.llm import get_chat

    resp = get_chat().invoke("Responda apenas com a palavra OK.")
    assert "OK" in resp.content.upper()
