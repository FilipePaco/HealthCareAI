"""Testes da API (ver tests/TEST_PLAN.md). Auth/health são unitários; dados são integração."""
from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import settings
from src.etl.clean import SELECTED_COLUMNS, clean
from src.etl.load import load_dataframe

client = TestClient(app)
HEADERS = {"X-API-Key": settings.api_key}


def _seed(engine) -> None:
    row = {col: None for col in SELECTED_COLUMNS}
    row.update({"DT_SIN_PRI": "15/05/2024", "EVOLUCAO": 2, "HOSPITAL": 1, "UTI": 1, "VACINA_COV": 1})
    cleaned, _ = clean(pd.DataFrame([row]), today="2024-06-15")
    load_dataframe(engine, cleaned)


def test_health_no_auth() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_protected_requires_api_key() -> None:
    assert client.get("/metrics").status_code == 401


def test_metrics_with_key(engine) -> None:
    _seed(engine)
    resp = client.get("/metrics", headers=HEADERS)
    assert resp.status_code == 200
    assert "taxa_mortalidade" in resp.json()["metrics"]


def test_report_and_audit_roundtrip(engine) -> None:
    _seed(engine)
    report = client.post("/reports", headers=HEADERS)
    assert report.status_code == 200
    report_id = report.json()["report_id"]

    audit = client.get(f"/audit/{report_id}", headers=HEADERS)
    assert audit.status_code == 200
    assert len(audit.json()["trail"]) >= 1
