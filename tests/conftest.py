"""Fixtures compartilhadas. O `engine` pula os testes se o Postgres não estiver acessível."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from src.db.models import get_engine


@pytest.fixture(scope="session")
def engine():
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - queremos pular em qualquer falha de conexão
        pytest.skip(f"Postgres indisponível para testes de integração: {exc}")
    return eng
