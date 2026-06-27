"""Trilho de auditoria das decisões do agente (P2, R6.x).

Toda chamada de tool/LLM e cada métrica passam por aqui e ficam persistidas em `audit_log`
(JSONB), recuperáveis por `report_id`. Armazena apenas agregados/metadados — nunca microdados
(P4); bytes (ex.: PNG de gráfico) são reduzidos ao seu tamanho.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine


def new_report_id() -> str:
    return uuid.uuid4().hex


def init_audit(engine: Engine) -> None:
    """Cria a tabela de auditoria se não existir."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                    event TEXT NOT NULL,
                    data JSONB
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_report ON audit_log(report_id)"))


def _jsonable(obj: Any) -> Any:
    """Converte para algo serializável; reduz bytes a tamanho (sem vazar conteúdo/microdados)."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, bytes):
        return {"_bytes_len": len(obj)}
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


@dataclass
class AuditTrail:
    """Acumula e persiste o trilho de uma geração de relatório."""

    engine: Engine
    report_id: str = field(default_factory=new_report_id)

    def record(self, event: str, data: dict | None = None) -> None:
        payload = json.dumps(_jsonable(data or {}), default=str, ensure_ascii=False)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO audit_log (report_id, event, data) "
                    "VALUES (:r, :e, CAST(:d AS JSONB))"
                ),
                {"r": self.report_id, "e": event, "d": payload},
            )

    def record_call(self, event: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Registra entrada, executa `fn`, registra saída e devolve o resultado."""
        self.record(f"{event}.input", {"args": _jsonable(args), "kwargs": _jsonable(kwargs)})
        result = fn(*args, **kwargs)
        self.record(f"{event}.output", {"result": _jsonable(result)})
        return result

    def entries(self) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, ts, event, data FROM audit_log WHERE report_id = :r ORDER BY id"),
                {"r": self.report_id},
            )
            return [
                {"id": r.id, "ts": r.ts.isoformat(), "event": r.event, "data": r.data} for r in rows
            ]
