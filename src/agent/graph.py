"""Orquestrador LangGraph (ADR-02): grafo de estado auditável nó a nó.

Fluxo: gather_metrics (determinístico) -> gather_news (tool-calling do LLM + RAG, ADR-11) ->
compose (LLM com grounding). Os gráficos são derivados deterministicamente das mesmas views e
servidos pelos endpoints /charts, fora do caminho de raciocínio do LLM.

Todo consumo de LLM/busca é contabilizado por um `UsageTracker` (P9) e anexado ao relatório.

A auditoria acontece em duas camadas (ADR-13): o `AuditTrail` grava o trilho de conformidade no
Postgres (obrigatório) e, se `TRACING_ENABLED` estiver ligado, os callbacks do Langfuse produzem o
trace operacional (opcional). A `config` do LangChain é passada explicitamente de nó em nó para que
o trace saia completo; quando o tracing está desligado ela é `{}` e nada muda.
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
from src.governance.tracing import flush as flush_tracing
from src.governance.tracing import runnable_config
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


def _fallback_news(
    metrics: dict, trail: AuditTrail, usage: UsageTracker, config: dict | None = None
) -> list[dict]:
    """Busca determinística (R4.7): query formulada pelo LLM, ou termo padrão, sem laço de tools."""
    try:
        query = formulate_query(metrics, usage, config=config)
        trail.record("news_fallback.formulate_query", {"search_query": query})
    except Exception as exc:  # noqa: BLE001 - sem LLM, usa termo padrão
        query = DEFAULT_QUERY
        trail.record("news_fallback.formulate_query.error", {"error": str(exc), "fallback": query})
    scenario = scenario_text(metrics)
    k = settings.news_retrieve_k
    news = gather_relevant_news(
        scenario_query=scenario, search_query=query, k=k, usage=usage, config=config
    )
    usage.record_search(1)
    if not news and query != DEFAULT_QUERY:
        news = gather_relevant_news(
            scenario_query=scenario, search_query=DEFAULT_QUERY, k=k, usage=usage, config=config
        )
        usage.record_search(1)
        trail.record("news_fallback.retry", {"search_query": DEFAULT_QUERY, "count": len(news)})
    trail.record("news_fallback.gather", {"count": len(news), "sources": [n.get("url") for n in news]})
    return news


def _news_node(trail: AuditTrail, usage: UsageTracker, config: dict | None = None):
    def node(state: ReportState) -> dict:
        metrics = state["metrics"]
        try:  # agência real: laço de tool-calling (ADR-11)
            news = run_news_agent(
                metrics, trail, usage, k=settings.news_retrieve_k, config=config
            )
        except Exception as exc:  # noqa: BLE001 - tool-calling indisponível: degrada (R4.7/R4.4)
            trail.record("news_agent.error", {"error": str(exc)})
            try:
                news = _fallback_news(metrics, trail, usage, config=config)
            except Exception as exc2:  # noqa: BLE001 - até a busca falhou -> relatório sem notícias
                news = []
                trail.record("gather_news.error", {"error": str(exc2)})
        return {"news": news}

    return node


def _compose_node(trail: AuditTrail, usage: UsageTracker, config: dict | None = None):
    def node(state: ReportState) -> dict:
        try:
            data = compose_commentary(
                state["metrics"], state.get("news", []), usage, config=config
            ).model_dump()
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


def build_graph(engine: Engine, trail: AuditTrail, usage: UsageTracker, config: dict | None = None):
    sg = StateGraph(ReportState)
    sg.add_node("metrics", _metrics_node(engine, trail))
    sg.add_node("news", _news_node(trail, usage, config))
    sg.add_node("compose", _compose_node(trail, usage, config))
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
    # Camada 2 (ADR-13): `{}` quando o tracing está desligado — nada no fluxo muda.
    config = runnable_config(trail.report_id)
    final = build_graph(engine, trail, usage, config).invoke(
        {"report_id": trail.report_id}, config=config
    )
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
    flush_tracing()  # despacha o trace; falha aqui nunca afeta o relatório (R11.3)
    return report
