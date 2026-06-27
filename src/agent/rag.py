"""RAG efêmero sobre as notícias (ADR-08, R4.6).

Por requisição: embedda os trechos retornados pela busca, indexa em memória
(`InMemoryVectorStore`) e recupera o top-k mais relevante ao cenário. O índice é
reconstruído a cada relatório e descartado — adequado a notícia efêmera/tempo real.
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from src.agent.llm import get_embeddings
from src.agent.tools.news_tool import Article, search_news


def build_index(articles: list[Article]) -> InMemoryVectorStore:
    """Indexa em memória os artigos que tenham conteúdo."""
    store = InMemoryVectorStore(get_embeddings())
    docs = [
        Document(
            page_content=a.content,
            metadata={"title": a.title, "url": a.url, "date": a.date},
        )
        for a in articles
        if a.content
    ]
    if docs:
        store.add_documents(docs)
    return store


def retrieve(store: InMemoryVectorStore, query: str, k: int = 4) -> list[dict]:
    """Top-k trechos mais relevantes ao cenário, já com fonte e data."""
    results = store.similarity_search(query, k=k)
    return [
        {
            "content": d.page_content,
            "title": d.metadata.get("title"),
            "url": d.metadata.get("url"),
            "date": d.metadata.get("date"),
        }
        for d in results
    ]


def rank_articles(articles: list[Article], scenario_query: str, k: int = 4) -> list[dict]:
    """Indexa artigos já obtidos e recupera o top-k relevante ao cenário (RAG efêmero).

    Usado pelo laço de tool-calling (ADR-11), que acumula artigos de várias buscas. Se os
    embeddings falharem, devolve os artigos crus (sem ranqueamento), preservando o fluxo.
    """
    if not articles:
        return []
    try:
        store = build_index(articles)
        return retrieve(store, scenario_query, k=k)
    except Exception:  # noqa: BLE001 - embeddings indisponíveis: usa artigos crus
        return [
            {"content": a.content, "title": a.title, "url": a.url, "date": a.date}
            for a in articles[:k]
        ]


def gather_relevant_news(
    scenario_query: str, search_query: str | None = None, k: int = 4, max_results: int = 6
) -> list[dict]:
    """Pipeline completo: busca (Tavily) -> índice efêmero -> retrieve top-k.

    `search_query` é o termo formulado pelo agente; `scenario_query` descreve o cenário das
    métricas e é usado na recuperação semântica. Lista vazia aciona o fallback (R4.4).
    """
    articles = search_news(search_query or scenario_query, max_results=max_results)
    return rank_articles(articles, scenario_query, k=k)
