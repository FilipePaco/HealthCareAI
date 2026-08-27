"""Testes da camada 2 de observabilidade (ver tests/TEST_PLAN.md).

O ponto central é o **contrato de degradação** (R11.3): desligado, sem credenciais, ou com o SDK
quebrado, a aplicação segue idêntica e a camada 1 não é afetada. Nenhum teste aqui fala com a rede.
"""
from __future__ import annotations

import pytest

from src.config import settings
from src.governance import tracing


@pytest.fixture
def tracing_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tracing_enabled", False)


@pytest.fixture
def tracing_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tracing_enabled", True)
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")


def test_inactive_when_disabled(tracing_off) -> None:
    assert tracing.tracing_active() is False
    assert tracing.get_callbacks("a" * 32) == []
    assert tracing.runnable_config("a" * 32) == {}


def test_inactive_without_credentials(monkeypatch) -> None:
    """Habilitado mas sem chaves: não pode tentar tracing nem quebrar (R11.3)."""
    monkeypatch.setattr(settings, "tracing_enabled", True)
    monkeypatch.setattr(settings, "langfuse_public_key", None)
    monkeypatch.setattr(settings, "langfuse_secret_key", None)
    assert tracing.tracing_active() is False
    assert tracing.runnable_config("a" * 32) == {}


def test_degrades_when_sdk_unavailable(tracing_on, monkeypatch) -> None:
    """SDK ausente/incompatível -> lista vazia, sem exceção (R11.3)."""
    monkeypatch.setattr(
        tracing, "_handler", lambda report_id: (_ for _ in ()).throw(ImportError("sem langfuse"))
    )
    assert tracing.get_callbacks("a" * 32) == []
    assert tracing.runnable_config("a" * 32) == {}


def test_flush_never_raises(tracing_on, monkeypatch) -> None:
    tracing.flush()  # SDK não instalado no ambiente de teste: precisa ser silencioso


def test_flush_noop_when_disabled(tracing_off) -> None:
    tracing.flush()


def test_metadata_carries_report_id(tracing_on) -> None:
    """R11.2: o report_id é o elo entre o trilho de auditoria e o trace."""
    meta = tracing.trace_metadata("deadbeef" * 4)
    assert meta["langfuse_session_id"] == "deadbeef" * 4
    assert "srag-report" in meta["langfuse_tags"]


def test_report_id_is_valid_trace_id() -> None:
    """O report_id (uuid4().hex) tem o formato de trace id do OpenTelemetry."""
    from src.governance.audit import new_report_id

    assert tracing._TRACE_ID_RE.match(new_report_id())


def test_runnable_config_shape(tracing_on, monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(tracing, "_handler", lambda report_id: sentinel)
    config = tracing.runnable_config("a" * 32)
    assert config["callbacks"] == [sentinel]
    assert config["metadata"]["langfuse_session_id"] == "a" * 32
