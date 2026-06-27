"""Orquestrador LangGraph (ADR-02): grafo de estado auditável nó a nó.

Fluxo: gather_metrics (determinístico) -> gather_news (tool-calling do LLM + RAG, ADR-11) ->
compose (LLM com grounding). Os gráficos são derivados deterministicamente das mesmas views e
servidos pelos endpoints /charts, fora do caminho de raciocínio do LLM.

Todo consumo de LLM/busca é contabilizado por um `UsageTracker` (P9) e anexado ao relatório.
"""
from __future__ import annotations

from dataclasses import asdict

from langgraph.graph import END, StateGraph
from sqlalchemy.engine import Engine

from src.agent.news_agent import DEFAULT_QUERY, run_news_agent
from src.agent.prompts import scenario_text
from src.agent.rag import gather_relevant_news
from src.agent.state import ReportState
from src.config import settings
from src.db import queries as q
from src.db.reports_store import init_reports, save_report
from src.governance.audit import AuditTrail, init_audit
from src.governance.usage import UsageTracker
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


_LLM_UNAVAILABLE = (
    "Comentário do agente indisponível no momento (modelo de linguagem temporariamente "
    "inacessível). As métricas e os gráficos permanecem válidos."
)


def _fallback_news(metrics: dict, trail: AuditTrail, usage: UsageTracker) -> list[dict]:
    """Busca determinística (R4.7): query formulada pelo LLM, ou termo padrão, sem laço de tools."""
    try:
        query = formulate_query(metrics, usage)
        trail.record("news_fallback.formulate_query", {"search_query": query})
    except Exception as exc:  # noqa: BLE001 - sem LLM, usa termo padrão
        query = DEFAULT_QUERY
        trail.record("news_fallback.formulate_query.error", {"error": str(exc), "fallback": query})
    scenario = scenario_text(metrics)
    k = settings.news_retrieve_k
    news = gather_relevant_news(scenario_query=scenario, search_query=query, k=k)
    usage.record_search(1)
    if not news and query != DEFAULT_QUERY:
        news = gather_relevant_news(scenario_query=scenario, search_query=DEFAULT_QUERY, k=k)
        usage.record_search(1)
        trail.record("news_fallback.retry", {"search_query": DEFAULT_QUERY, "count": len(news)})
    trail.record("news_fallback.gather", {"count": len(news), "sources": [n.get("url") for n in news]})
    return news


def _news_node(trail: AuditTrail, usage: UsageTracker):
    def node(state: ReportState) -> dict:
        metrics = state["metrics"]
        try:  # agência real: laço de tool-calling (ADR-11)
            news = run_news_agent(metrics, trail, usage, k=settings.news_retrieve_k)
        except Exception as exc:  # noqa: BLE001 - tool-calling indisponível: degrada (R4.7/R4.4)
            trail.record("news_agent.error", {"error": str(exc)})
            try:
                news = _fallback_news(metrics, trail, usage)
            except Exception as exc2:  # noqa: BLE001 - até a busca falhou -> relatório sem notícias
                news = []
                trail.record("gather_news.error", {"error": str(exc2)})
        return {"news": news}

    return node


def _compose_node(trail: AuditTrail, usage: UsageTracker):
    def node(state: ReportState) -> dict:
        try:
            data = compose_commentary(state["metrics"], state.get("news", []), usage).model_dump()
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


def build_graph(engine: Engine, trail: AuditTrail, usage: UsageTracker):
    sg = StateGraph(ReportState)
    sg.add_node("metrics", _metrics_node(engine, trail))
    sg.add_node("news", _news_node(trail, usage))
    sg.add_node("compose", _compose_node(trail, usage))
    sg.set_entry_point("metrics")
    sg.add_edge("metrics", "news")
    sg.add_edge("news", "compose")
    sg.add_edge("compose", END)
    return sg.compile()


def generate_report(engine: Engine, report_id: str | None = None) -> dict:
    """Roda o grafo e monta o relatório completo (métricas + comentário + fontes + uso + auditoria)."""
    init_audit(engine)
    init_reports(engine)
    trail = AuditTrail(engine) if report_id is None else AuditTrail(engine, report_id=report_id)
    usage = UsageTracker()
    final = build_graph(engine, trail, usage).invoke({"report_id": trail.report_id})
    usage_data = usage.as_dict()
    trail.record("usage", usage_data)
    report = {
        "report_id": trail.report_id,
        "data_ref": final.get("data_ref"),
        "metrics": final.get("metrics", {}),
        "charts": {"daily": "/charts/daily.png", "monthly": "/charts/monthly.png"},
        "commentary": final.get("commentary"),
        "sources": final.get("sources", []),
        "usage": usage_data,
        "disclaimer": DISCLAIMER,
    }
    save_report(engine, report)
    return report
