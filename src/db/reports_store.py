"""Persistência dos relatórios gerados (para `GET /reports/{id}` e export em PDF consistente)."""
from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.engine import Engine


def init_reports(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    payload JSONB NOT NULL
                )
                """
            )
        )


def save_report(engine: Engine, report: dict) -> None:
    payload = json.dumps(report, default=str, ensure_ascii=False)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO reports (report_id, payload) VALUES (:id, CAST(:p AS JSONB)) "
                "ON CONFLICT (report_id) DO UPDATE SET payload = EXCLUDED.payload"
            ),
            {"id": report["report_id"], "p": payload},
        )


def get_report(engine: Engine, report_id: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT payload FROM reports WHERE report_id = :id"), {"id": report_id}
        ).first()
    return row[0] if row else None
