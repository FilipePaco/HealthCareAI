"""Orquestrador LangGraph (ADR-02): grafo de estado auditável nó a nó.

Fluxo: gather_metrics (determinístico) -> gather_news (agência + RAG) -> compose (LLM com grounding).
Os gráficos são derivados deterministicamente das mesmas views e servidos pelos endpoints /charts,
fora do caminho de raciocínio do LLM.
"""
from __future__ import annotations

from dataclasses import asdict

from langgraph.graph import END, StateGraph
from sqlalchemy.engine import Engine

from src.agent.prompts import scenario_text
from src.agent.rag import gather_relevant_news
from src.agent.state import ReportState
from src.db import queries as q
from src.db.reports_store import init_reports, save_report
from src.governance.audit import AuditTrail, init_audit
from src.report.composer import compose_commentary, formulate_query

DISCLAIMER = "PoC de caráter educacional — não constitui orientação médica."


def _metrics_node(engine: Engine, trail: AuditTrail):
    def node(state: ReportState) -> dict:
        with engine.connect() as conn:
            ref = q.get_data_ref(conn)
            metrics = {name: asdict(q.run_metric(conn, name, data_ref=ref)) for name in q.METRICS}
        trail.record("gather_metrics", {"data_ref": ref, "metrics": metrics})
        return {"data_ref": ref, "metrics": metrics}

    return node


_DEFAULT_QUERY = "SRAG síndrome respiratória aguda grave notícias Brasil"
_LLM_UNAVAILABLE = (
    "Comentário do agente indisponível no momento (modelo de linguagem temporariamente "
    "inacessível). As métricas e os gráficos permanecem válidos."
)


def _news_node(trail: AuditTrail):
    def node(state: ReportState) -> dict:
        metrics = state["metrics"]
        try:  # agência: LLM formula a busca (degrada para query padrão se o LLM falhar)
            query = formulate_query(metrics)
            trail.record("formulate_query", {"search_query": query})
        except Exception as exc:  # noqa: BLE001
            query = _DEFAULT_QUERY
            trail.record("formulate_query.error", {"error": str(exc), "fallback": query})
        scenario = scenario_text(metrics)
        try:
            news = gather_relevant_news(scenario_query=scenario, search_query=query, k=4)
            if not news and query != _DEFAULT_QUERY:
                # agência: refina a busca uma vez com termos amplos (R4.5)
                news = gather_relevant_news(scenario_query=scenario, search_query=_DEFAULT_QUERY, k=4)
                trail.record("gather_news.retry", {"search_query": _DEFAULT_QUERY, "count": len(news)})
            trail.record("gather_news", {"count": len(news), "sources": [n.get("url") for n in news]})
        except Exception as exc:  # noqa: BLE001 - falha de busca/embeddings cai no fallback (R4.4)
            news = []
            trail.record("gather_news.error", {"error": str(exc)})
        return {"search_query": query, "news": news}

    return node


def _compose_node(trail: AuditTrail):
    def node(state: ReportState) -> dict:
        try:
            data = compose_commentary(state["metrics"], state.get("news", [])).model_dump()
        except Exception as exc:  # noqa: BLE001 - LLM indisponível -> relatório degradado, não quebra
            trail.record("compose.error", {"error": str(exc)})
            return {
                "commentary": {"per_metric": [], "synthesis": _LLM_UNAVAILABLE, "sources": []},
                "sources": [],
            }
        sources = sorted(
            {s for c in data["per_metric"] for s in c["sources"]} | set(data["sources"])
        )
        trail.record("compose", {"commentary": data, "sources": sources})
        return {"commentary": data, "sources": sources}

    return node


def build_graph(engine: Engine, trail: AuditTrail):
    sg = StateGraph(ReportState)
    sg.add_node("metrics", _metrics_node(engine, trail))
    sg.add_node("news", _news_node(trail))
    sg.add_node("compose", _compose_node(trail))
    sg.set_entry_point("metrics")
    sg.add_edge("metrics", "news")
    sg.add_edge("news", "compose")
    sg.add_edge("compose", END)
    return sg.compile()


def generate_report(engine: Engine, report_id: str | None = None) -> dict:
    """Roda o grafo e monta o relatório completo (métricas + comentário + fontes + auditoria)."""
    init_audit(engine)
    init_reports(engine)
    trail = AuditTrail(engine) if report_id is None else AuditTrail(engine, report_id=report_id)
    final = build_graph(engine, trail).invoke({"report_id": trail.report_id})
    report = {
        "report_id": trail.report_id,
        "data_ref": final.get("data_ref"),
        "metrics": final.get("metrics", {}),
        "charts": {"daily": "/charts/daily.png", "monthly": "/charts/monthly.png"},
        "commentary": final.get("commentary"),
        "sources": final.get("sources", []),
        "disclaimer": DISCLAIMER,
    }
    save_report(engine, report)
    return report
