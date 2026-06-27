"""Testes do UsageTracker (ver tests/TEST_PLAN.md) — puros, sem rede/banco."""
from __future__ import annotations

from src.config import settings
from src.governance.usage import UsageTracker


class _Msg:
    """Simula uma resposta LangChain com usage_metadata."""

    def __init__(self, inp: int, out: int) -> None:
        self.usage_metadata = {"input_tokens": inp, "output_tokens": out}


def test_usage_accumulates_llm_tokens() -> None:
    u = UsageTracker()
    u.record_llm(_Msg(100, 40))
    u.record_llm(_Msg(50, 10))
    assert u.llm_calls == 2
    assert u.input_tokens == 150
    assert u.output_tokens == 50
    assert u.total_tokens == 200


def test_usage_counts_searches() -> None:
    u = UsageTracker()
    u.record_search()
    u.record_search(2)
    assert u.tavily_searches == 3


def test_usage_handles_message_without_metadata() -> None:
    u = UsageTracker()
    u.record_llm(object())  # sem usage_metadata -> conta a chamada, 0 tokens
    assert u.llm_calls == 1
    assert u.total_tokens == 0


def test_usage_estimated_cost() -> None:
    u = UsageTracker(input_tokens=1_000_000, output_tokens=1_000_000, tavily_searches=2)
    expected = (
        settings.llm_input_cost_per_1m
        + settings.llm_output_cost_per_1m
        + 2 * settings.tavily_cost_per_search
    )
    assert u.estimated_cost_usd() == round(expected, 6)


def test_usage_as_dict_shape() -> None:
    u = UsageTracker(llm_calls=3, input_tokens=10, output_tokens=5, tavily_searches=1)
    d = u.as_dict()
    assert set(d) == {
        "llm_calls",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "tavily_searches",
        "estimated_cost_usd",
        "estimate",
    }
    assert d["total_tokens"] == 15
    assert d["estimate"] is True
