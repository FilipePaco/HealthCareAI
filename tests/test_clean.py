"""Testes da limpeza/seleção do ETL (ver tests/TEST_PLAN.md).

Dados sintéticos com resultado conhecido; sem rede nem banco.
"""
from __future__ import annotations

import pandas as pd

from src.etl.clean import SELECTED_COLUMNS, clean, select_columns

TODAY = "2024-06-01"


def base_row(**overrides: object) -> dict[str, object]:
    """Linha válida mínima; sobrescreva campos para exercitar cada regra."""
    row: dict[str, object] = {col: None for col in SELECTED_COLUMNS}
    row["DT_SIN_PRI"] = "01/05/2024"
    row.update(overrides)
    return row


def test_select_columns_drops_identifiers_and_extras() -> None:
    df = pd.DataFrame(
        [{"DT_SIN_PRI": "01/01/2023", "NM_PACIENT": "Fulano", "UTI": 1, "COLUNA_EXTRA": 7}]
    )
    out = select_columns(df)
    assert "NM_PACIENT" not in out.columns
    assert "COLUNA_EXTRA" not in out.columns
    assert {"DT_SIN_PRI", "UTI"} <= set(out.columns)


def test_drops_rows_without_dt_sin_pri() -> None:
    df = pd.DataFrame([base_row(), base_row(DT_SIN_PRI="lixo"), base_row(DT_SIN_PRI=None)])
    _, report = clean(df, today=TODAY)
    assert report.rows_in == 3
    assert report.rows_out == 1
    assert report.dropped_missing_sin_pri == 2


def test_categorical_out_of_domain_becomes_9() -> None:
    df = pd.DataFrame([base_row(UTI=7), base_row(UTI=1)])
    out, report = clean(df, today=TODAY)
    assert set(out["UTI"].dropna().tolist()) <= {1, 2, 9}
    assert (out["UTI"] == 9).sum() == 1
    assert report.categoricals_normalized["UTI"] == 1


def test_classi_fin_out_of_domain_becomes_na() -> None:
    # 9 não é código válido de CLASSI_FIN (domínio {1..5}) -> vira NA
    df = pd.DataFrame([base_row(CLASSI_FIN=9), base_row(CLASSI_FIN=5)])
    out, _ = clean(df, today=TODAY)
    assert out["CLASSI_FIN"].isna().sum() == 1
    assert (out["CLASSI_FIN"] == 5).sum() == 1


def test_dates_out_of_bounds_invalidated() -> None:
    df = pd.DataFrame(
        [
            base_row(DT_SIN_PRI="01/01/2030"),  # futura -> NaT -> linha cai
            base_row(DT_SIN_PRI="01/01/2019"),  # anterior a 2021 -> NaT -> linha cai
            base_row(DT_SIN_PRI="01/05/2024"),  # válida
        ]
    )
    _, report = clean(df, today=TODAY)
    assert report.rows_out == 1
    assert report.dropped_missing_sin_pri == 2


def test_interna_before_sintomas_invalidated() -> None:
    df = pd.DataFrame([base_row(DT_SIN_PRI="10/05/2024", DT_INTERNA="01/05/2024")])
    out, report = clean(df, today=TODAY)
    assert pd.isna(out.iloc[0]["DT_INTERNA"])
    assert report.interna_before_sintomas == 1


def test_cleaning_report_counts() -> None:
    df = pd.DataFrame([base_row(), base_row(DT_SIN_PRI=None)])
    _, report = clean(df, today=TODAY)
    assert report.rows_in == 2
    assert report.rows_out == 1
    assert report.rows_in == report.rows_out + report.dropped_missing_sin_pri


def test_idempotent_on_clean_input() -> None:
    df = pd.DataFrame([base_row(UTI=1, EVOLUCAO=2, DT_INTERNA="03/05/2024")])
    once, _ = clean(df, today=TODAY)
    # Reaplicar sobre a saída (datas já são datetime, categóricos já normalizados) não deve quebrar
    # nem alterar o número de linhas.
    twice, report2 = clean(once.copy(), today=TODAY)
    assert report2.rows_out == len(once)
    assert len(twice) == len(once)
