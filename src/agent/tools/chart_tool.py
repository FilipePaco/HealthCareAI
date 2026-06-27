"""Tool de gráficos: casos diários (30d) e mensais (12m) -> PNG (R3.1–R3.3).

Render server-side (backend Agg, determinístico) para embutir no PDF e servir via API.
As funções de densificação são puras (testáveis sem rede/banco); recebem as séries já
vindas das views (P1) e preenchem com zero os períodos sem casos para uma curva contínua.
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")  # sem display; render para bytes
import matplotlib.pyplot as plt  # noqa: E402  (precisa vir após use("Agg"))

from src.db import queries as q

Series = list[tuple[date, int]]


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    total = d.month - 1 + n
    return date(d.year + total // 12, total % 12 + 1, 1)


def densify_daily(series: Series, end: date, days: int = 30) -> Series:
    """Preenche os últimos `days` dias (até `end`) com zero onde não há casos."""
    counts = {d: c for d, c in series}
    start = end - timedelta(days=days - 1)
    return [(start + timedelta(days=i), counts.get(start + timedelta(days=i), 0)) for i in range(days)]


def densify_monthly(series: Series, end: date, months: int = 12) -> Series:
    """Preenche os últimos `months` meses (até o mês de `end`) com zero onde não há casos."""
    counts = {_month_start(d): c for d, c in series}
    start = _add_months(_month_start(end), -(months - 1))
    keys = [_add_months(start, i) for i in range(months)]
    return [(k, counts.get(k, 0)) for k in keys]


def render_bar(labels: list[str], values: list[int], title: str, ylabel: str = "casos") -> bytes:
    """Renderiza um gráfico de barras e devolve os bytes do PNG."""
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(range(len(values)), values, color="#2a6f97")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.margins(x=0.01)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def daily_chart(series: Series, data_ref: date, days: int = 30) -> bytes:
    pairs = densify_daily(series, data_ref, days)
    labels = [d.strftime("%d/%m") for d, _ in pairs]
    return render_bar(labels, [c for _, c in pairs], f"Casos diários de SRAG — últimos {days} dias")


def monthly_chart(series: Series, data_ref: date, months: int = 12) -> bytes:
    pairs = densify_monthly(series, data_ref, months)
    labels = [d.strftime("%m/%Y") for d, _ in pairs]
    return render_bar(labels, [c for _, c in pairs], f"Casos mensais de SRAG — últimos {months} meses")


def build_charts(conn, data_ref: date) -> dict[str, bytes]:
    """Gera os dois gráficos a partir das views (séries determinísticas)."""
    daily = q.serie_diaria(conn, data_ref, days=30)
    monthly = q.serie_mensal(conn, data_ref, months=12)
    return {
        "daily": daily_chart(daily, data_ref, days=30),
        "monthly": monthly_chart(monthly, data_ref, months=12),
    }
