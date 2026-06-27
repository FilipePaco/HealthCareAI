"""Carga idempotente do CSV curado no PostgreSQL (P6, R1.5).

Fluxo: lê CSV -> `clean()` -> grava na tabela `srag_cases` -> (re)cria as views.
Recarregar não duplica dados (TRUNCATE antes do insert).
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.db.models import DDL_TABLE, DDL_VIEWS, TABLE, get_engine
from src.etl.clean import SELECTED_COLUMNS, CleaningReport, clean


def init_schema(engine: Engine) -> None:
    """Cria a tabela e as views se não existirem."""
    with engine.begin() as conn:
        conn.execute(DDL_TABLE)
        for view in DDL_VIEWS:
            conn.execute(view)


def load_dataframe(engine: Engine, df: pd.DataFrame) -> int:
    """Grava o DataFrame curado (idempotente) e recria as views. Retorna nº de linhas."""
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    cols = [c.lower() for c in SELECTED_COLUMNS if c.lower() in out.columns]
    out = out[cols]

    with engine.begin() as conn:
        conn.execute(DDL_TABLE)
        conn.execute(text(f"TRUNCATE {TABLE}"))
    out.to_sql(TABLE, engine, if_exists="append", index=False)
    with engine.begin() as conn:
        for view in DDL_VIEWS:
            conn.execute(view)
    return len(out)


def run_etl(
    csv_path: str, engine: Engine | None = None, today: object = None, **read_kwargs: object
) -> CleaningReport:
    """Pipeline completo: CSV -> limpeza -> carga. Retorna o relatório de limpeza."""
    engine = engine or get_engine()
    df = pd.read_csv(csv_path, sep=";", dtype=str, **read_kwargs)
    cleaned, report = clean(df, today=today)
    load_dataframe(engine, cleaned)
    return report
