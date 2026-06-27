"""Cálculo determinístico das métricas via SQL parametrizado (P1) + whitelist (P5).

O LLM NUNCA escreve nem executa SQL. Toda consulta de métrica passa por `run_metric`,
que só aceita nomes registrados em METRICS — qualquer outro é rejeitado (R7.1).

Definições em `.kiro/specs/srag-report-agent/data-and-metrics.md` §4. As janelas usam
o critério **half-open** `(ref - N, ref]`, garantindo exatamente N dias por janela.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.config import settings


@dataclass
class Metric:
    """Resultado auditável de uma métrica: valor + numerador/denominador + nota."""

    name: str
    value: float | None
    numerator: int
    denominator: int
    note: str = ""


def _ratio(numerator: int, denominator: int) -> float | None:
    """Percentual com guarda de divisão por zero (R2.6)."""
    return None if denominator == 0 else round(numerator / denominator * 100, 2)


def get_data_ref(conn: Connection) -> date | None:
    """Data de referência = maior DT_SIN_PRI presente (dados são batch, não tempo real)."""
    return conn.execute(text("SELECT MAX(dt_sin_pri) FROM srag_cases")).scalar()


def taxa_aumento_casos(
    conn: Connection, *, data_ref: date, window_days: int | None = None, **_: object
) -> Metric:
    window = window_days or settings.report_increase_window_days
    sql = text(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE dt_sin_pri >  :ref - make_interval(days => :w)
                  AND dt_sin_pri <= :ref
            ) AS recentes,
            COUNT(*) FILTER (
                WHERE dt_sin_pri >  :ref - make_interval(days => :w2)
                  AND dt_sin_pri <= :ref - make_interval(days => :w)
            ) AS anteriores
        FROM srag_cases
        """
    )
    row = conn.execute(sql, {"ref": data_ref, "w": window, "w2": 2 * window}).one()
    recentes, anteriores = int(row.recentes), int(row.anteriores)
    return Metric(
        "taxa_aumento_casos",
        None if anteriores == 0 else round((recentes - anteriores) / anteriores * 100, 2),
        recentes,
        anteriores,
        f"Janelas half-open de {window} dias ancoradas em {data_ref}.",
    )


def taxa_mortalidade(conn: Connection, **_: object) -> Metric:
    sql = text(
        """
        SELECT
            COUNT(*) FILTER (WHERE evolucao = 2)        AS obitos,
            COUNT(*) FILTER (WHERE evolucao IN (1, 2))  AS desfechos
        FROM srag_cases
        """
    )
    row = conn.execute(sql).one()
    obitos, desfechos = int(row.obitos), int(row.desfechos)
    return Metric(
        "taxa_mortalidade",
        _ratio(obitos, desfechos),
        obitos,
        desfechos,
        "CFR: óbitos por SRAG sobre desfechos conhecidos (cura ou óbito).",
    )


def taxa_ocupacao_uti(conn: Connection, **_: object) -> Metric:
    sql = text(
        """
        SELECT
            COUNT(*) FILTER (WHERE uti = 1 AND hospital = 1)          AS uti_sim,
            COUNT(*) FILTER (WHERE hospital = 1 AND uti IN (1, 2))    AS internados
        FROM srag_cases
        """
    )
    row = conn.execute(sql).one()
    uti_sim, internados = int(row.uti_sim), int(row.internados)
    return Metric(
        "taxa_ocupacao_uti",
        _ratio(uti_sim, internados),
        uti_sim,
        internados,
        "Proporção de internados que necessitaram UTI (não é ocupação de leitos).",
    )


def taxa_vacinacao(conn: Connection, **_: object) -> Metric:
    sql = text(
        """
        SELECT
            COUNT(*) FILTER (WHERE vacina_cov = 1)        AS vacinados,
            COUNT(*) FILTER (WHERE vacina_cov IN (1, 2))  AS conhecidos
        FROM srag_cases
        """
    )
    row = conn.execute(sql).one()
    vacinados, conhecidos = int(row.vacinados), int(row.conhecidos)
    return Metric(
        "taxa_vacinacao",
        _ratio(vacinados, conhecidos),
        vacinados,
        conhecidos,
        "Vacinação COVID entre os casos de SRAG (não é a população geral).",
    )


def serie_diaria(conn: Connection, data_ref: date, days: int = 30) -> list[tuple[date, int]]:
    sql = text(
        """
        SELECT dia, casos FROM v_casos_diarios
        WHERE dia > :ref - make_interval(days => :d) AND dia <= :ref
        ORDER BY dia
        """
    )
    return [(r.dia, int(r.casos)) for r in conn.execute(sql, {"ref": data_ref, "d": days})]


def serie_mensal(conn: Connection, data_ref: date, months: int = 12) -> list[tuple[date, int]]:
    sql = text(
        """
        SELECT mes, casos FROM v_casos_mensais
        WHERE mes >  (date_trunc('month', :ref) - make_interval(months => :m))::date
          AND mes <= date_trunc('month', :ref)::date
        ORDER BY mes
        """
    )
    return [(r.mes, int(r.casos)) for r in conn.execute(sql, {"ref": data_ref, "m": months})]


# Whitelist de métricas (P5): único ponto de entrada permitido para cálculo de métrica.
METRICS = {
    "taxa_aumento_casos": taxa_aumento_casos,
    "taxa_mortalidade": taxa_mortalidade,
    "taxa_ocupacao_uti": taxa_ocupacao_uti,
    "taxa_vacinacao": taxa_vacinacao,
}


def run_metric(conn: Connection, name: str, **kwargs: object) -> Metric:
    """Executa uma métrica da whitelist. Nome fora da whitelist é rejeitado (R7.1)."""
    if name not in METRICS:
        raise ValueError(f"Métrica não permitida (fora da whitelist): {name!r}")
    return METRICS[name](conn, **kwargs)
