"""Testes da tool de gráficos (ver tests/TEST_PLAN.md). Puro: sem rede nem banco."""
from __future__ import annotations

from datetime import date

from src.agent.tools.chart_tool import (
    daily_chart,
    densify_daily,
    densify_monthly,
    monthly_chart,
    render_bar,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_densify_daily_fills_missing_with_zero() -> None:
    series = [(date(2024, 6, 1), 4), (date(2024, 5, 31), 2)]
    out = densify_daily(series, date(2024, 6, 1), days=5)
    assert out == [
        (date(2024, 5, 28), 0),
        (date(2024, 5, 29), 0),
        (date(2024, 5, 30), 0),
        (date(2024, 5, 31), 2),
        (date(2024, 6, 1), 4),
    ]


def test_densify_monthly_fills_12_months() -> None:
    series = [(date(2024, 6, 10), 4), (date(2024, 5, 3), 2)]
    out = densify_monthly(series, date(2024, 6, 15), months=3)
    assert out == [(date(2024, 4, 1), 0), (date(2024, 5, 1), 2), (date(2024, 6, 1), 4)]


def test_render_bar_returns_png() -> None:
    png = render_bar(["a", "b", "c"], [1, 2, 3], "titulo")
    assert png.startswith(PNG_MAGIC)
    assert len(png) > 100


def test_daily_and_monthly_charts_png() -> None:
    series = [(date(2024, 6, 1), 4), (date(2024, 5, 10), 2)]
    assert daily_chart(series, date(2024, 6, 1)).startswith(PNG_MAGIC)
    assert monthly_chart(series, date(2024, 6, 1)).startswith(PNG_MAGIC)


def test_charts_handle_empty_series() -> None:
    assert daily_chart([], date(2024, 6, 1)).startswith(PNG_MAGIC)
    assert monthly_chart([], date(2024, 6, 1)).startswith(PNG_MAGIC)
