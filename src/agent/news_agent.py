"""Laço de tool-calling de notícias (ADR-11, R4.5/R4.7/R4.8).

A agência do agente vive aqui: a busca é exposta como **ferramenta chamável pelo LLM**
(`bind_tools` → `buscar_noticias`). O modelo formula a query, lê os resultados e **decide** se
encerra ou refina e busca de novo, até `NEWS_AGENT_MAX_ITERS`. Cada iteração é auditada (P2) e
contabilizada (P9). Os artigos acumulados passam pelo RAG efêmero para o top-k relevante.

Métricas e gráficos seguem determinísticos (P1) — a agência é restrita a este nó (ADR-09).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from src.agent.llm import get_chat
from src.agent.prompts import SYSTEM_NEWS_AGENT, news_agent_user_prompt, scenario_text
from src.agent.rag import rank_articles
from src.agent.tools.news_tool import Article, search_news
from src.config import settings
from src.governance.audit import AuditTrail
from src.governance.usage import UsageTracker

DEFAULT_QUERY = "SRAG síndrome respiratória aguda grave notícias Brasil"


@tool
def buscar_noticias(query: str) -> str:
    """Busca notícias recentes na web sobre SRAG (síndrome respiratória aguda grave) no Brasil.

    Args:
        query: termos de busca curtos, em português, derivados do cenário das métricas.
    """
    return _format_results(search_news(query))


def _format_results(articles: list[Article]) -> str:
    """Resumo compacto dos resultados devolvido ao modelo (limita tokens)."""
    if not articles:
        return "Nenhum resultado relevante encontrado para esta query."
    linhas = []
    for a in articles[:6]:
        trecho = (a.content or "")[:200]
        linhas.append(f"- [{a.url}] {a.title} ({a.date}): {trecho}")
    return "\n".join(linhas)


def _dedupe(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    out: list[Article] = []
    for a in articles:
        key = a.url or a.title
        if key and key not in seen:
            seen.add(key)
            out.append(a)
    return out


def run_news_agent(
    metrics: dict, trail: AuditTrail, usage: UsageTracker, k: int = 4
) -> list[dict]:
    """Roda o laço de tool-calling e devolve o top-k de notícias (RAG sobre o acumulado).

    Levanta exceção se nem o primeiro passo do LLM funcionar (provedor sem suporte a tools, cota):
    o nó de notícias trata isso degradando para a busca determinística (R4.7).
    """
    scenario = scenario_text(metrics)
    llm = get_chat().bind_tools([buscar_noticias])
    messages = [SystemMessage(SYSTEM_NEWS_AGENT), HumanMessage(news_agent_user_prompt(metrics))]
    collected: list[Article] = []
    max_iters = settings.news_agent_max_iters

    for i in range(max_iters):
        try:
            ai = llm.invoke(messages)
        except Exception as exc:  # noqa: BLE001 - cota/indisponibilidade no meio do laço
            trail.record("news_agent.llm_error", {"iteration": i, "error": str(exc)})
            if collected:
                break  # já temos material: segue para o RAG com o que foi coletado
            raise  # nada coletado: deixa o nó cair no fallback determinístico (R4.7)
        usage.record_llm(ai)
        messages.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            trail.record("news_agent.stop", {"iteration": i, "reason": "modelo encerrou a busca"})
            break
        for tc in tool_calls:
            query = ((tc.get("args") or {}).get("query") or "").strip()
            articles = search_news(query) if query else []
            usage.record_search(1)
            collected.extend(articles)
            trail.record(
                "news_agent.tool_call", {"iteration": i, "query": query, "count": len(articles)}
            )
            messages.append(ToolMessage(content=_format_results(articles), tool_call_id=tc.get("id", "")))
    else:
        trail.record("news_agent.max_iters", {"max_iters": max_iters})

    if not collected:
        # Modelo não chamou a tool ou as buscas vieram vazias: uma busca padrão evita ficar sem contexto.
        collected = search_news(DEFAULT_QUERY)
        usage.record_search(1)
        trail.record("news_agent.default_search", {"query": DEFAULT_QUERY, "count": len(collected)})

    news = rank_articles(_dedupe(collected), scenario, k=k)
    trail.record("news_agent.selected", {"count": len(news), "sources": [n.get("url") for n in news]})
    return news
