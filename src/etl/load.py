"""Carga idempotente do CSV (sintético ou real do DATASUS) no PostgreSQL (P6, R1.5).

Lê em chunks e apenas as colunas pertinentes (memória controlada em arquivos de ~200 MB),
aplica `clean()` chunk a chunk e grava. Uso real:
`python -m src.etl.load --year 2024`  ou  `python -m src.etl.load --csv data/arquivo.csv`.
"""
from __future__ import annotations

import argparse

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.db.models import DDL_TABLE, DDL_VIEWS, TABLE, get_engine
from src.etl.clean import SELECTED_COLUMNS, CleaningReport, clean

_KEEP = set(SELECTED_COLUMNS)


def init_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(DDL_TABLE)
        for view in DDL_VIEWS:
            conn.execute(view)


def _create_views(engine: Engine) -> None:
    with engine.begin() as conn:
        for view in DDL_VIEWS:
            conn.execute(view)


def _append(engine: Engine, df: pd.DataFrame) -> int:
    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    cols = [c.lower() for c in SELECTED_COLUMNS if c.lower() in out.columns]
    out = out[cols]
    out.to_sql(TABLE, engine, if_exists="append", index=False)
    return len(out)


def load_dataframe(engine: Engine, df: pd.DataFrame) -> int:
    """Grava o DataFrame curado (idempotente) e recria as views. Retorna nº de linhas."""
    with engine.begin() as conn:
        conn.execute(DDL_TABLE)
        conn.execute(text(f"TRUNCATE {TABLE}"))
    n = _append(engine, df)
    _create_views(engine)
    return n


def run_etl(
    csv_path: str,
    engine: Engine | None = None,
    today: object = None,
    chunksize: int = 100_000,
    encoding: str = "latin-1",
    sep: str = ";",
    nrows: int | None = None,
) -> CleaningReport:
    """Pipeline completo em chunks: CSV -> limpeza -> carga. Retorna o relatório agregado."""
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLE}"))

    agg = CleaningReport()
    reader = pd.read_csv(
        csv_path,
        sep=sep,
        dtype=str,
        encoding=encoding,
        usecols=lambda c: c in _KEEP,
        chunksize=chunksize,
        nrows=nrows,
    )
    for chunk in reader:
        cleaned, rep = clean(chunk, today=today)
        _append(engine, cleaned)
        agg.rows_in += rep.rows_in
        agg.rows_out += rep.rows_out
        agg.dropped_missing_sin_pri += rep.dropped_missing_sin_pri
    _create_views(engine)
    return agg


def main() -> None:
    parser = argparse.ArgumentParser(description="Carrega o CSV de SRAG no Postgres.")
    parser.add_argument("--csv", help="caminho do CSV local")
    parser.add_argument("--year", help="baixa e carrega o ano (ex.: 2024)")
    parser.add_argument("--limit", type=int, help="nº máximo de linhas (teste rápido)")
    args = parser.parse_args()

    if args.year:
        from src.etl.download import ensure_year

        path = str(ensure_year(args.year))
    elif args.csv:
        path = args.csv
    else:
        parser.error("informe --csv ou --year")

    report = run_etl(path, nrows=args.limit)
    print(
        f"ETL concluída: {report.rows_in} linhas lidas -> {report.rows_out} carregadas "
        f"(sem DT_SIN_PRI válida: {report.dropped_missing_sin_pri})."
    )


if __name__ == "__main__":
    main()
