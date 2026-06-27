"""Endpoints da API (API-first). Dados agregados + gráficos + relatório + auditoria.

O relatório (`POST /reports`) já monta métricas, séries e trilho de auditoria; o comentário
do LLM e as fontes de notícia entram quando o agente (Tavily+LLM) for plugado.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.engine import Engine

from src.agent.graph import generate_report
from src.agent.tools import chart_tool
from src.api.security import require_api_key
from src.db import queries as q
from src.db.models import get_engine
from src.db.reports_store import get_report
from src.governance.audit import AuditTrail, init_audit
from src.report.pdf import build_pdf

router = APIRouter()
_engine: Engine | None = None

DISCLAIMER = "PoC de caráter educacional — não constitui orientação médica."


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def _all_metrics(conn, data_ref: date | None) -> dict[str, dict]:
    return {name: asdict(q.run_metric(conn, name, data_ref=data_ref)) for name in q.METRICS}


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/metrics", dependencies=[Depends(require_api_key)])
def metrics() -> dict:
    with engine().connect() as conn:
        data_ref = q.get_data_ref(conn)
        return {"data_ref": data_ref, "metrics": _all_metrics(conn, data_ref)}


@router.get("/data/daily", dependencies=[Depends(require_api_key)])
def data_daily() -> dict:
    with engine().connect() as conn:
        ref = q.get_data_ref(conn)
        series = q.serie_diaria(conn, ref) if ref else []
        return {"data_ref": ref, "series": [{"dia": d.isoformat(), "casos": c} for d, c in series]}


@router.get("/data/monthly", dependencies=[Depends(require_api_key)])
def data_monthly() -> dict:
    with engine().connect() as conn:
        ref = q.get_data_ref(conn)
        series = q.serie_mensal(conn, ref) if ref else []
        return {"data_ref": ref, "series": [{"mes": d.isoformat(), "casos": c} for d, c in series]}


@router.get("/charts/daily.png", dependencies=[Depends(require_api_key)])
def chart_daily() -> Response:
    with engine().connect() as conn:
        ref = q.get_data_ref(conn)
        series = q.serie_diaria(conn, ref) if ref else []
    return Response(chart_tool.daily_chart(series, ref or date.today()), media_type="image/png")


@router.get("/charts/monthly.png", dependencies=[Depends(require_api_key)])
def chart_monthly() -> Response:
    with engine().connect() as conn:
        ref = q.get_data_ref(conn)
        series = q.serie_mensal(conn, ref) if ref else []
    return Response(chart_tool.monthly_chart(series, ref or date.today()), media_type="image/png")


@router.post("/reports", dependencies=[Depends(require_api_key)])
def create_report() -> dict:
    """Roda o agente LangGraph: métricas + notícias(RAG) + comentário com grounding."""
    return generate_report(engine())


@router.get("/reports/{report_id}", dependencies=[Depends(require_api_key)])
def read_report(report_id: str) -> dict:
    report = get_report(engine(), report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="relatório não encontrado")
    return report


@router.get("/reports/{report_id}/pdf", dependencies=[Depends(require_api_key)])
def report_pdf(report_id: str) -> Response:
    report = get_report(engine(), report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="relatório não encontrado")
    charts: dict[str, bytes] = {}
    ref = report.get("data_ref")
    if ref:
        d = date.fromisoformat(str(ref)[:10])
        with engine().connect() as conn:
            charts["daily"] = chart_tool.daily_chart(q.serie_diaria(conn, d), d)
            charts["monthly"] = chart_tool.monthly_chart(q.serie_mensal(conn, d), d)
    pdf = build_pdf(report, charts)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="relatorio_{report_id}.pdf"'},
    )


@router.get("/audit/{report_id}", dependencies=[Depends(require_api_key)])
def get_audit(report_id: str) -> dict:
    eng = engine()
    init_audit(eng)
    return {"report_id": report_id, "trail": AuditTrail(eng, report_id=report_id).entries()}
