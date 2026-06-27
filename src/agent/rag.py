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


def gather_relevant_news(
    scenario_query: str, search_query: str | None = None, k: int = 4, max_results: int = 6
) -> list[dict]:
    """Pipeline completo: busca (Tavily) -> índice efêmero -> retrieve top-k.

    `search_query` é o termo formulado pelo agente; `scenario_query` descreve o cenário das
    métricas e é usado na recuperação semântica. Lista vazia aciona o fallback (R4.4).
    """
    articles = search_news(search_query or scenario_query, max_results=max_results)
    if not articles:
        return []
    store = build_index(articles)
    return retrieve(store, scenario_query, k=k)
