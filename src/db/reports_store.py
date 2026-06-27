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


def aggregate_usage(engine: Engine, limit: int = 50) -> dict:
    """Soma o uso/custo de LLM e busca dos relatórios persistidos (R10.3, P9)."""
    totals_sql = text(
        """
        SELECT
          count(*) AS reports,
          coalesce(sum((payload->'usage'->>'llm_calls')::int), 0) AS llm_calls,
          coalesce(sum((payload->'usage'->>'input_tokens')::int), 0) AS input_tokens,
          coalesce(sum((payload->'usage'->>'output_tokens')::int), 0) AS output_tokens,
          coalesce(sum((payload->'usage'->>'total_tokens')::int), 0) AS total_tokens,
          coalesce(sum((payload->'usage'->>'tavily_searches')::int), 0) AS tavily_searches,
          coalesce(sum((payload->'usage'->>'estimated_cost_usd')::numeric), 0) AS estimated_cost_usd
        FROM reports
        WHERE payload ? 'usage'
        """
    )
    recent_sql = text(
        """
        SELECT report_id, created_at, payload->'usage' AS usage
        FROM reports
        WHERE payload ? 'usage'
        ORDER BY created_at DESC
        LIMIT :lim
        """
    )
    with engine.connect() as conn:
        t = conn.execute(totals_sql).first()
        rows = conn.execute(recent_sql, {"lim": limit}).all()
    return {
        "totals": {
            "reports": t.reports,
            "llm_calls": t.llm_calls,
            "input_tokens": t.input_tokens,
            "output_tokens": t.output_tokens,
            "total_tokens": t.total_tokens,
            "tavily_searches": t.tavily_searches,
            "estimated_cost_usd": round(float(t.estimated_cost_usd), 6),
            "estimate": True,
        },
        "by_report": [
            {"report_id": r.report_id, "created_at": r.created_at.isoformat(), "usage": r.usage}
            for r in rows
        ],
    }
