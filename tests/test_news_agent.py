"""Testes do laço de tool-calling de notícias (ver tests/TEST_PLAN.md).

Usam um LLM *fake* (sem rede/tokens): validam que o laço chama a ferramenta enquanto o modelo
pede, encerra quando ele para, respeita o limite de iterações e que o nó degrada se o agente falha.
"""
from __future__ import annotations

import pytest

from src.agent import news_agent
from src.agent.tools.news_tool import Article
from src.governance.usage import UsageTracker


class _FakeAI:
    def __init__(self, tool_calls=None) -> None:
        self.tool_calls = tool_calls or []
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
        self.content = ""


class _FakeChat:
    """Devolve, a cada invoke, o próximo _FakeAI do roteiro (repete o último)."""

    def __init__(self, script) -> None:
        self.script = list(script)
        self.calls = 0

    def bind_tools(self, tools):  # noqa: ANN001
        return self

    def invoke(self, messages):  # noqa: ANN001
        ai = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return ai


class _FakeTrail:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record(self, event: str, data: dict | None = None) -> None:
        self.events.append((event, data or {}))


def _events(trail: _FakeTrail) -> list[str]:
    return [e for e, _ in trail.events]


def _patch(monkeypatch, script) -> None:
    monkeypatch.setattr(news_agent, "get_chat", lambda: _FakeChat(script))
    monkeypatch.setattr(
        news_agent, "search_news", lambda q: [Article("T", f"http://x/{q[:5]}", "2024-06-01", "c")]
    )
    # evita embeddings reais: rankeia devolvendo os artigos como dicts
    monkeypatch.setattr(
        news_agent,
        "rank_articles",
        lambda arts, scenario, k=4: [{"url": a.url, "title": a.title} for a in arts[:k]],
    )


_TC = [{"name": "buscar_noticias", "args": {"query": "srag uti"}, "id": "1"}]


def test_news_agent_loops_until_model_stops(monkeypatch) -> None:
    # 1ª resposta pede a tool; 2ª encerra (sem tool_calls)
    _patch(monkeypatch, [_FakeAI(_TC), _FakeAI([])])
    usage = UsageTracker()
    trail = _FakeTrail()
    news = news_agent.run_news_agent({"taxa_mortalidade": {"value": 9}}, trail, usage)
    assert news and news[0]["url"].startswith("http")
    assert usage.llm_calls == 2          # uma chamada com tool + uma de encerramento
    assert usage.tavily_searches == 1    # uma única tool_call executada
    assert "news_agent.tool_call" in _events(trail)
    assert "news_agent.stop" in _events(trail)
    assert "news_agent.selected" in _events(trail)


def test_news_agent_records_each_iteration(monkeypatch) -> None:
    _patch(monkeypatch, [_FakeAI(_TC), _FakeAI(_TC), _FakeAI([])])
    usage = UsageTracker()
    trail = _FakeTrail()
    news_agent.run_news_agent({"m": {"value": 1}}, trail, usage)
    tool_calls = [d for e, d in trail.events if e == "news_agent.tool_call"]
    assert len(tool_calls) == 2
    assert {d["iteration"] for d in tool_calls} == {0, 1}


def test_news_agent_respects_max_iters(monkeypatch) -> None:
    monkeypatch.setattr(news_agent.settings, "news_agent_max_iters", 2)
    _patch(monkeypatch, [_FakeAI(_TC)])  # sempre pede tool -> nunca encerra sozinho
    usage = UsageTracker()
    trail = _FakeTrail()
    news_agent.run_news_agent({"m": {"value": 1}}, trail, usage)
    assert usage.llm_calls == 2
    assert usage.tavily_searches == 2
    assert "news_agent.max_iters" in _events(trail)


def test_news_agent_default_search_when_model_never_calls_tool(monkeypatch) -> None:
    _patch(monkeypatch, [_FakeAI([])])  # encerra de cara, sem coletar nada
    usage = UsageTracker()
    trail = _FakeTrail()
    news = news_agent.run_news_agent({"m": {"value": 1}}, trail, usage)
    assert "news_agent.default_search" in _events(trail)
    assert usage.tavily_searches == 1
    assert news  # a busca padrão garante contexto


def test_news_agent_raises_when_first_call_fails(monkeypatch) -> None:
    class _Boom(_FakeChat):
        def invoke(self, messages):  # noqa: ANN001
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(news_agent, "get_chat", lambda: _Boom([_FakeAI([])]))
    with pytest.raises(RuntimeError):  # nada coletado -> propaga p/ o nó degradar (R4.7)
        news_agent.run_news_agent({"m": {"value": 1}}, _FakeTrail(), UsageTracker())


def test_news_node_falls_back_on_agent_error(monkeypatch) -> None:
    from src.agent import graph

    def _raise(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("tool-calling indisponível")

    monkeypatch.setattr(graph, "run_news_agent", _raise)
    monkeypatch.setattr(graph, "_fallback_news", lambda metrics, trail, usage: [{"url": "http://ok"}])

    node = graph._news_node(_FakeTrail(), UsageTracker())
    out = node({"metrics": {"m": {"value": 1}}})
    assert out == {"news": [{"url": "http://ok"}]}
