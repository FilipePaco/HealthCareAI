"""Limpeza e seleção de colunas do CSV de SRAG (DATASUS / SIVEP-Gripe).

Funções puras e testáveis (P6/P7). As definições de colunas e regras seguem
`.kiro/specs/srag-report-agent/data-and-metrics.md` (§3 seleção, §6 limpeza).

Regras principais:
- Mantém apenas as colunas pertinentes; descarta o resto (minimização, P4).
- Datas em formato DD/MM/AAAA; inválidas viram NaT.
- Datas fora de [MIN_VALID_DATE, today] são invalidadas (NaT).
- DT_INTERNA anterior a DT_SIN_PRI é invalidada (regra do dicionário).
- Categóricos fora do domínio viram 9-Ignorado (ou NA quando 9 não é válido).
- Linhas sem DT_SIN_PRI (data epidemiológica primária) são descartadas.
- Todas as contagens afetadas são reportadas para transparência (R1.3).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# --- Colunas selecionadas (P4) -------------------------------------------------
DATE_COLUMNS: list[str] = [
    "DT_SIN_PRI",
    "DT_NOTIFIC",
    "DT_INTERNA",
    "DT_ENTUTI",
    "DT_SAIDUTI",
    "DT_EVOLUCA",
    "DOSE_1_COV",
    "DOSE_2_COV",
]

# Categórico -> conjunto de códigos válidos (dicionário SIVEP-Gripe)
CATEGORICAL_DOMAINS: dict[str, set[int]] = {
    "HOSPITAL": {1, 2, 9},
    "UTI": {1, 2, 9},
    "EVOLUCAO": {1, 2, 3, 9},
    "CLASSI_FIN": {1, 2, 3, 4, 5},
    "VACINA_COV": {1, 2, 9},
    "VACINA": {1, 2, 9},
    "CS_SEXO": {1, 2, 9},
}

GEO_COLUMNS: list[str] = ["SG_UF", "SG_UF_NOT", "CO_MUN_RES"]
NUMERIC_COLUMNS: list[str] = ["NU_IDADE_N"]

SELECTED_COLUMNS: list[str] = (
    DATE_COLUMNS + list(CATEGORICAL_DOMAINS) + GEO_COLUMNS + NUMERIC_COLUMNS
)

UNKNOWN_CODE = 9
MIN_VALID_DATE = pd.Timestamp("2021-01-01")
MAX_AGE = 130
DATE_FORMAT = "%d/%m/%Y"


@dataclass
class CleaningReport:
    """Contagens de transparência sobre o que a limpeza afetou (R1.3)."""

    rows_in: int = 0
    rows_out: int = 0
    dropped_missing_sin_pri: int = 0
    interna_before_sintomas: int = 0
    invalid_dates_coerced: dict[str, int] = field(default_factory=dict)
    categoricals_normalized: dict[str, int] = field(default_factory=dict)


def select_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém só as colunas selecionadas presentes; descarta identificadores e extras (P4)."""
    keep = [col for col in SELECTED_COLUMNS if col in df.columns]
    return df[keep].copy()


def _coerce_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format=DATE_FORMAT, errors="coerce")


def parse_dates(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """Converte as colunas de data; conta valores não nulos que se tornaram inválidos."""
    for col in DATE_COLUMNS:
        if col not in df.columns:
            continue
        raw_present = df[col].notna() & (df[col].astype(str).str.strip() != "")
        parsed = _coerce_date(df[col])
        newly_invalid = int((raw_present & parsed.isna()).sum())
        report.invalid_dates_coerced[col] = newly_invalid
        df[col] = parsed
    return df


def apply_date_bounds(df: pd.DataFrame, report: CleaningReport, today: pd.Timestamp) -> pd.DataFrame:
    """Invalida (NaT) datas anteriores a MIN_VALID_DATE ou futuras."""
    for col in DATE_COLUMNS:
        if col not in df.columns:
            continue
        out_of_bounds = df[col].notna() & ((df[col] < MIN_VALID_DATE) | (df[col] > today))
        report.invalid_dates_coerced[col] = report.invalid_dates_coerced.get(col, 0) + int(
            out_of_bounds.sum()
        )
        df.loc[out_of_bounds, col] = pd.NaT
    return df


def apply_interna_rule(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """DT_INTERNA deve ser >= DT_SIN_PRI; caso contrário invalida (NaT)."""
    if "DT_INTERNA" not in df.columns or "DT_SIN_PRI" not in df.columns:
        return df
    invalid = df["DT_INTERNA"].notna() & df["DT_SIN_PRI"].notna() & (
        df["DT_INTERNA"] < df["DT_SIN_PRI"]
    )
    report.interna_before_sintomas = int(invalid.sum())
    df.loc[invalid, "DT_INTERNA"] = pd.NaT
    return df


def normalize_categoricals(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """Mapeia categóricos para inteiro; fora do domínio vira 9 (ou NA se 9 não for válido)."""
    for col, domain in CATEGORICAL_DOMAINS.items():
        if col not in df.columns:
            continue
        nums = pd.to_numeric(df[col], errors="coerce")
        in_domain = nums.isin(list(domain))
        report.categoricals_normalized[col] = int((~in_domain).sum())
        fill: object = UNKNOWN_CODE if UNKNOWN_CODE in domain else pd.NA
        df[col] = nums.where(in_domain, other=fill).astype("Int64")
    return df


def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Idade para inteiro; valores fora de [0, MAX_AGE] viram NA."""
    if "NU_IDADE_N" in df.columns:
        ages = pd.to_numeric(df["NU_IDADE_N"], errors="coerce")
        ages = ages.where((ages >= 0) & (ages <= MAX_AGE), other=pd.NA)
        df["NU_IDADE_N"] = ages.astype("Int64")
    return df


def clean(df: pd.DataFrame, today: object = None) -> tuple[pd.DataFrame, CleaningReport]:
    """Pipeline de limpeza completo. `today` permite testes determinísticos.

    Retorna o DataFrame curado e um CleaningReport com as contagens afetadas.
    """
    ref_today = pd.Timestamp(today).normalize() if today is not None else pd.Timestamp.now().normalize()
    report = CleaningReport(rows_in=len(df))

    df = select_columns(df)
    if "DT_SIN_PRI" not in df.columns:
        # Sem a data epidemiológica primária não há caso utilizável (entrada vazia ou coluna ausente).
        report.dropped_missing_sin_pri = report.rows_in
        return df.iloc[0:0].copy(), report
    df = parse_dates(df, report)
    df = apply_date_bounds(df, report, ref_today)
    df = apply_interna_rule(df, report)
    df = normalize_categoricals(df, report)
    df = coerce_numeric(df)

    before = len(df)
    df = df[df["DT_SIN_PRI"].notna()].copy().reset_index(drop=True)
    report.dropped_missing_sin_pri = before - len(df)
    report.rows_out = len(df)
    return df, report
