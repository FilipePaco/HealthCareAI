"""Esquema do banco curado (PostgreSQL) e fábrica de engine.

Tabela única `srag_cases` (colunas em minúsculas) + views de agregação que padronizam
as séries diária e mensal (P6). Acesso ao banco só por este módulo e por `queries.py`.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import settings

TABLE = "srag_cases"

DDL_TABLE = text(
    """
    CREATE TABLE IF NOT EXISTS srag_cases (
        dt_sin_pri DATE,
        dt_notific DATE,
        dt_interna DATE,
        dt_entuti  DATE,
        dt_saiduti DATE,
        dt_evoluca DATE,
        dose_1_cov DATE,
        dose_2_cov DATE,
        hospital   SMALLINT,
        uti        SMALLINT,
        evolucao   SMALLINT,
        classi_fin SMALLINT,
        vacina_cov SMALLINT,
        vacina     SMALLINT,
        cs_sexo    SMALLINT,
        sg_uf      VARCHAR(2),
        sg_uf_not  VARCHAR(2),
        co_mun_res VARCHAR(20),
        nu_idade_n SMALLINT
    );
    """
)

DDL_VIEWS = [
    text(
        """
        CREATE OR REPLACE VIEW v_casos_diarios AS
            SELECT dt_sin_pri AS dia, COUNT(*) AS casos
            FROM srag_cases
            WHERE dt_sin_pri IS NOT NULL
            GROUP BY dt_sin_pri
            ORDER BY dia;
        """
    ),
    text(
        """
        CREATE OR REPLACE VIEW v_casos_mensais AS
            SELECT date_trunc('month', dt_sin_pri)::date AS mes, COUNT(*) AS casos
            FROM srag_cases
            WHERE dt_sin_pri IS NOT NULL
            GROUP BY 1
            ORDER BY mes;
        """
    ),
]


def get_engine(url: str | None = None) -> Engine:
    """Cria um engine SQLAlchemy (default = settings.database_url)."""
    return create_engine(url or settings.database_url, future=True)
