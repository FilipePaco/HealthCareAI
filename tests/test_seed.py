"""Testes do gerador de dados sintéticos (puro)."""
from __future__ import annotations

from src.etl.clean import clean
from src.etl.seed import generate_raw


def test_generate_raw_count_and_columns() -> None:
    df = generate_raw(50)
    assert len(df) == 50
    assert "DT_SIN_PRI" in df.columns


def test_seed_is_cleanable() -> None:
    df = generate_raw(200)
    cleaned, report = clean(df)
    assert report.rows_in == 200
    assert report.rows_out > 0  # datas no último ano sobrevivem à limpeza
