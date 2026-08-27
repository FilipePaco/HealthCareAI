"""Embeddings do RAG entram na conta de custo (R10.5) — antes ficavam de fora.

Sem rede: os embeddings e o vector store são substituídos por dublês.
"""
from __future__ import annotations

from src.agent import rag
from src.agent.tools.news_tool import Article
from src.config import settings
from src.governance.usage import UsageTracker

_ARTICLES = [
    Article("UTI", "http://uti", "2024-06-01", "x" * 400),
    Article("Vacina", "http://vacina", "2024-06-01", "y" * 400),
]


class _FakeStore:
    def __init__(self, *_a, **_k) -> None:
        self.docs: list = []

    def add_documents(self, docs) -> None:  # noqa: ANN001
        self.docs.extend(docs)

    def similarity_search(self, query, k=4):  # noqa: ANN001
        return self.docs[:k]


def _patch(monkeypatch) -> None:
    monkeypatch.setattr(rag, "get_embeddings", lambda: object())
    monkeypatch.setattr(rag, "InMemoryVectorStore", _FakeStore)


def test_build_index_records_embeddings(monkeypatch) -> None:
    _patch(monkeypatch)
    usage = UsageTracker()
    rag.build_index(_ARTICLES, usage)
    assert usage.embedding_calls == 1
    # 800 caracteres / ~4 por token
    assert usage.embedding_tokens == 800 // settings.embedding_chars_per_token


def test_rank_articles_counts_documents_and_query(monkeypatch) -> None:
    _patch(monkeypatch)
    usage = UsageTracker()
    out = rag.rank_articles(_ARTICLES, "cenário de UTI", k=2, usage=usage)
    assert len(out) == 2
    assert usage.embedding_calls == 2  # documentos + query
    assert usage.embedding_tokens > 0


def test_embeddings_enter_estimated_cost() -> None:
    """O custo estimado precisa refletir os embeddings (era subestimado antes)."""
    usage = UsageTracker(embedding_tokens=1_000_000)
    assert usage.estimated_cost_usd() == round(settings.embedding_cost_per_1m, 6)


def test_rank_articles_empty_is_noop(monkeypatch) -> None:
    _patch(monkeypatch)
    usage = UsageTracker()
    assert rag.rank_articles([], "cenário", usage=usage) == []
    assert usage.embedding_calls == 0
