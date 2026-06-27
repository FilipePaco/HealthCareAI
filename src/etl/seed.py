"""Carga de dados sintéticos para usar/testar a solução sem o CSV real do DATASUS.

Gera casos distribuídos no último ano (para popular os gráficos de 30 dias e 12 meses) e
carrega via o mesmo pipeline de limpeza. Uso: `python -m src.etl.seed --rows 5000`.
"""
from __future__ import annotations

import argparse
import random
from datetime import date, timedelta

import pandas as pd

from src.db.models import get_engine
from src.etl.clean import SELECTED_COLUMNS, clean
from src.etl.load import load_dataframe


def generate_raw(rows: int = 5000, ref: date | None = None, seed: int = 42) -> pd.DataFrame:
    """DataFrame "cru" (strings/códigos) simulando o formato do DATASUS."""
    rng = random.Random(seed)
    ref = ref or date.today()
    registros = []
    for _ in range(rows):
        d = ref - timedelta(days=rng.randint(0, 364))
        row = {c: None for c in SELECTED_COLUMNS}
        row["DT_SIN_PRI"] = d.strftime("%d/%m/%Y")
        row["HOSPITAL"] = rng.choice([1, 1, 1, 2])
        row["UTI"] = rng.choice([1, 2, 2, 9])
        row["EVOLUCAO"] = rng.choice([1, 1, 1, 2, 9])
        row["VACINA_COV"] = rng.choice([1, 1, 2, 9])
        row["CLASSI_FIN"] = rng.choice([1, 2, 4, 5, 5])
        row["CS_SEXO"] = rng.choice([1, 2])
        row["NU_IDADE_N"] = rng.randint(0, 95)
        registros.append(row)
    return pd.DataFrame(registros)


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula o banco com casos sintéticos de SRAG.")
    parser.add_argument("--rows", type=int, default=5000)
    args = parser.parse_args()

    df = generate_raw(args.rows)
    cleaned, report = clean(df)
    total = load_dataframe(get_engine(), cleaned)
    print(f"Carregados {total} registros sintéticos (de {report.rows_in} gerados).")


if __name__ == "__main__":
    main()
