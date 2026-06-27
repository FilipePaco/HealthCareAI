"""Testes de integração das métricas (Postgres real) — ver tests/TEST_PLAN.md.

Dados sintéticos com resultado conhecido; provam o determinismo das métricas (P1).
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.db import queries as q
from src.etl.clean import SELECTED_COLUMNS, clean
from src.etl.load import init_schema, load_dataframe

TODAY = "2024-06-15"


def _raw(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {col: None for col in SELECTED_COLUMNS}
    row["DT_SIN_PRI"] = "15/05/2024"
    row.update(overrides)
    return row


def _load(engine, raw_rows: list[dict[str, object]]) -> None:
    cleaned, _ = clean(pd.DataFrame(raw_rows), today=TODAY)
    load_dataframe(engine, cleaned)


# Dataset com respostas conhecidas para mortalidade, UTI e vacinação:
#  r1 h1/u1/evo2/vac1 | r2 h1/u1/evo2/vac1 | r3 h1/u2/evo2/vac1 | r4 h1/u2/evo1/vac2 | r5 h2/u9/evo9/vac9
SEVERITY_ROWS = [
    _raw(HOSPITAL=1, UTI=1, EVOLUCAO=2, VACINA_COV=1),
    _raw(HOSPITAL=1, UTI=1, EVOLUCAO=2, VACINA_COV=1),
    _raw(HOSPITAL=1, UTI=2, EVOLUCAO=2, VACINA_COV=1),
    _raw(HOSPITAL=1, UTI=2, EVOLUCAO=1, VACINA_COV=2),
    _raw(HOSPITAL=2, UTI=9, EVOLUCAO=9, VACINA_COV=9),
]


def test_taxa_mortalidade_conhecida(engine) -> None:
    _load(engine, SEVERITY_ROWS)
    with engine.connect() as conn:
        m = q.taxa_mortalidade(conn)
    assert (m.numerator, m.denominator) == (3, 4)  # óbitos=3, desfechos=4
    assert m.value == 75.0


def test_taxa_ocupacao_uti_conhecida(engine) -> None:
    _load(engine, SEVERITY_ROWS)
    with engine.connect() as conn:
        m = q.taxa_ocupacao_uti(conn)
    assert (m.numerator, m.denominator) == (2, 4)  # uti=1 -> 2, internados -> 4
    assert m.value == 50.0


def test_taxa_vacinacao_conhecida(engine) -> None:
    _load(engine, SEVERITY_ROWS)
    with engine.connect() as conn:
        m = q.taxa_vacinacao(conn)
    assert (m.numerator, m.denominator) == (3, 4)  # vac=1 -> 3, conhecidos -> 4
    assert m.value == 75.0


def test_taxa_aumento_casos_janelas(engine) -> None:
    # 4 casos recentes (01/06) e 2 anteriores (10/05); data_ref = 01/06.
    rows = [_raw(DT_SIN_PRI="01/06/2024") for _ in range(4)]
    rows += [_raw(DT_SIN_PRI="10/05/2024") for _ in range(2)]
    _load(engine, rows)
    with engine.connect() as conn:
        data_ref = q.get_data_ref(conn)
        m = q.taxa_aumento_casos(conn, data_ref=data_ref, window_days=14)
    assert (m.numerator, m.denominator) == (4, 2)
    assert m.value == 100.0


def test_metrica_sem_dados_retorna_none(engine) -> None:
    init_schema(engine)
    with engine.begin() as conn:
        conn.execute(q.text("TRUNCATE srag_cases"))  # tabela vazia
    with engine.connect() as conn:
        assert q.taxa_mortalidade(conn).value is None
        assert q.taxa_vacinacao(conn).value is None


def test_series_diaria_e_mensal(engine) -> None:
    rows = [_raw(DT_SIN_PRI="01/06/2024") for _ in range(4)]
    rows += [_raw(DT_SIN_PRI="10/05/2024") for _ in range(2)]
    _load(engine, rows)
    with engine.connect() as conn:
        data_ref = q.get_data_ref(conn)
        diaria = q.serie_diaria(conn, data_ref, days=30)
        mensal = q.serie_mensal(conn, data_ref, months=12)
    assert sum(c for _, c in diaria) == 6
    assert {c for _, c in diaria} == {4, 2}
    assert sum(c for _, c in mensal) == 6
    assert len(mensal) == 2  # maio e junho


def test_whitelist_rejeita_metrica_desconhecida() -> None:
    with pytest.raises(ValueError, match="whitelist"):
        q.run_metric(None, "DROP TABLE srag_cases")  # type: ignore[arg-type]


def test_carga_idempotente(engine) -> None:
    _load(engine, SEVERITY_ROWS)
    _load(engine, SEVERITY_ROWS)  # recarrega o mesmo dado
    with engine.connect() as conn:
        total = conn.execute(q.text("SELECT COUNT(*) FROM srag_cases")).scalar()
    assert total == len(SEVERITY_ROWS)  # não duplicou
