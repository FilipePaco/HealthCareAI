"""Persistência de relatórios + endpoints GET /reports/{id} e /pdf (integração c/ Postgres)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings
from src.db.reports_store import get_report, init_reports, save_report

client = TestClient(app)
HEADERS = {"X-API-Key": settings.api_key}

FAKE = {
    "report_id": "testabc",
    "data_ref": None,  # sem data_ref -> PDF é gerado sem gráficos (não precisa de dados em srag_cases)
    "metrics": {"taxa_mortalidade": {"value": 50.0, "numerator": 1, "denominator": 2, "note": ""}},
    "commentary": {
        "per_metric": [{"metric": "taxa_mortalidade", "explanation": "x", "sources": []}],
        "synthesis": "sintese",
        "sources": [],
    },
    "sources": [],
    "disclaimer": "PoC — não constitui orientação médica.",
}


def test_report_roundtrip(engine) -> None:
    init_reports(engine)
    save_report(engine, FAKE)
    stored = get_report(engine, "testabc")
    assert stored["metrics"]["taxa_mortalidade"]["value"] == 50.0


def test_report_get_and_pdf_endpoints(engine) -> None:
    init_reports(engine)
    save_report(engine, FAKE)
    assert client.get("/reports/testabc", headers=HEADERS).status_code == 200
    pdf = client.get("/reports/testabc/pdf", headers=HEADERS)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_report_404(engine) -> None:
    assert client.get("/reports/naoexiste", headers=HEADERS).status_code == 404
