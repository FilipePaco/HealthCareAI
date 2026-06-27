"""Testes da composição e do grafo (ver tests/TEST_PLAN.md).

`test_enforce_grounding_*` é puro; o e2e real usa DB + Gemini + Tavily (gasta tokens).
"""
from __future__ import annotations

import pytest

from src.config import settings
from src.report.composer import MetricComment, ReportCommentary, enforce_grounding


def _has(key: str | None) -> bool:
    return bool(key) and "your-" not in str(key)


def test_enforce_grounding_drops_unlisted_sources() -> None:
    commentary = ReportCommentary(
        per_metric=[
            MetricComment(
                metric="taxa_mortalidade",
                explanation="...",
                sources=["http://valida", "http://inventada"],
            )
        ],
        synthesis="...",
        sources=["http://inventada"],
    )
    out = enforce_grounding(commentary, allowed_urls={"http://valida"})
    assert out.per_metric[0].sources == ["http://valida"]
    assert out.sources == []  # fonte fora das notícias recuperadas foi removida


@pytest.mark.skipif(
    not (_has(settings.google_api_key) and _has(settings.tavily_api_key)),
    reason="requer GOOGLE_API_KEY e TAVILY_API_KEY",
)
def test_generate_report_real(engine) -> None:
    import pandas as pd

    from src.agent.graph import generate_report
    from src.db import queries as q
    from src.etl.clean import SELECTED_COLUMNS, clean
    from src.etl.load import load_dataframe

    rows = []
    for evo, uti, vac in [(2, 1, 1), (2, 1, 2), (1, 2, 1), (1, 2, 2), (2, 1, 1)]:
        r = {c: None for c in SELECTED_COLUMNS}
        r.update({"DT_SIN_PRI": "15/05/2024", "HOSPITAL": 1, "EVOLUCAO": evo, "UTI": uti, "VACINA_COV": vac})
        rows.append(r)
    cleaned, _ = clean(pd.DataFrame(rows), today="2024-06-15")
    load_dataframe(engine, cleaned)

    report = generate_report(engine)

    assert report["commentary"] is not None
    per_metric = report["commentary"]["per_metric"]
    assert {c["metric"] for c in per_metric} == set(q.METRICS)  # uma explicação por métrica
    assert isinstance(report["commentary"]["synthesis"], str) and report["commentary"]["synthesis"]
    assert all(s.startswith("http") for s in report["sources"])  # só fontes reais sobreviveram
    assert "orientação médica" in report["disclaimer"]
