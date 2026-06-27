"""Download dos CSVs reais de SRAG do Open DATASUS (SIVEP-Gripe).

Arquivos grandes (~100-200 MB/ano), hospedados no S3 do dado aberto do SUS. Salvos em `data/`
(gitignored). Uso: `python -m src.etl.download --year 2024`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import httpx

# Recursos do dataset "srag-2021-a-2024" (URLs do bucket de dados abertos do SUS).
RESOURCES: dict[str, str] = {
    "2024": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2024/INFLUD24-03-03-2025.csv",
}

DATA_DIR = Path("data")


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "healthcare-srag-agent"}
    with httpx.stream("GET", url, headers=headers, timeout=None, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as out:
            for chunk in resp.iter_bytes(1 << 20):  # 1 MB
                out.write(chunk)
    return dest


def ensure_year(year: str = "2024", data_dir: Path = DATA_DIR) -> Path:
    """Baixa o CSV do ano (se ainda não existir localmente) e retorna o caminho."""
    if year not in RESOURCES:
        raise ValueError(f"Ano sem URL conhecida: {year}. Disponíveis: {list(RESOURCES)}")
    dest = data_dir / f"INFLUD{year[2:]}.csv"
    if not dest.exists():
        download(RESOURCES[year], dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa o CSV real de SRAG do DATASUS.")
    parser.add_argument("--year", default="2024", choices=list(RESOURCES))
    args = parser.parse_args()
    path = ensure_year(args.year)
    print(f"CSV disponível em: {path} ({path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
