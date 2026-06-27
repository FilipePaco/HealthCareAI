"""Testes do render de PDF (puro: ReportLab + Matplotlib, sem rede/banco)."""
from __future__ import annotations

from src.agent.tools.chart_tool import render_bar
from src.report.pdf import build_pdf

SAMPLE = {
    "report_id": "x",
    "data_ref": "2024-05-15",
    "metrics": {
        "taxa_mortalidade": {"value": 75.0, "numerator": 3, "denominator": 4, "note": "CFR"},
        "taxa_aumento_casos": {"value": None, "numerator": 0, "denominator": 0, "note": ""},
    },
    "commentary": {
        "per_metric": [
            {"metric": "taxa_mortalidade", "explanation": "Índice elevado.", "sources": ["http://a"]}
        ],
        "synthesis": "Cenário de gravidade.",
        "sources": ["http://a"],
    },
    "sources": ["http://a"],
    "disclaimer": "PoC — não constitui orientação médica.",
}


def test_build_pdf_returns_pdf() -> None:
    assert build_pdf(SAMPLE).startswith(b"%PDF")


def test_build_pdf_with_charts() -> None:
    png = render_bar(["a", "b"], [1, 2], "titulo")
    out = build_pdf(SAMPLE, {"daily": png, "monthly": png})
    assert out.startswith(b"%PDF")
    assert len(out) > 1000
