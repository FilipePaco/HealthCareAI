"""Testes do trilho de auditoria (ver tests/TEST_PLAN.md). Integração c/ Postgres."""
from __future__ import annotations

from src.governance.audit import AuditTrail, init_audit


def test_audit_records_and_reads_back(engine) -> None:
    init_audit(engine)
    trail = AuditTrail(engine)
    trail.record("metric", {"name": "taxa_mortalidade", "value": 75.0})
    entries = trail.entries()
    assert len(entries) == 1
    assert entries[0]["event"] == "metric"
    assert entries[0]["data"]["value"] == 75.0


def test_record_call_logs_input_output(engine) -> None:
    init_audit(engine)
    trail = AuditTrail(engine)
    result = trail.record_call("dobro", lambda x: x * 2, 21)
    assert result == 42
    events = [e["event"] for e in trail.entries()]
    assert "dobro.input" in events
    assert "dobro.output" in events


def test_audit_scoped_by_report(engine) -> None:
    init_audit(engine)
    a = AuditTrail(engine)
    b = AuditTrail(engine)
    a.record("evento", {"x": 1})
    assert len(a.entries()) == 1
    assert len(b.entries()) == 0  # trilhos isolados por report_id


def test_audit_reduces_bytes(engine) -> None:
    init_audit(engine)
    trail = AuditTrail(engine)
    trail.record("grafico", {"png": b"\x89PNG fake bytes"})
    data = trail.entries()[-1]["data"]
    assert "_bytes_len" in data["png"]  # conteúdo não vaza; só o tamanho
