# Steering — Estrutura do Projeto

Estrutura-alvo do repositório (a implementar na fase de código). Reflete a separação
ETL ↔ runtime (P6) e a abordagem API-first.

```text
HealthCareAI/
├── .kiro/                         # Specs (SDD) — este diretório
│   ├── steering/                  # Princípios e convenções
│   └── specs/srag-report-agent/   # requirements, design, tasks
├── docs/
│   └── architecture/              # Diagrama conceitual (fonte + PDF exigido)
├── data/                          # CSV bruto (gitignored) e dicionário de dados
├── src/
│   ├── config.py                  # Settings (Pydantic Settings) — única fonte de config
│   ├── etl/                       # Pipeline offline e idempotente
│   │   ├── download.py            # obtenção do CSV do DATASUS
│   │   ├── clean.py               # seleção de colunas, tipagem, anonimização (P4)
│   │   └── load.py                # carga no Postgres + views de agregação
│   ├── db/
│   │   ├── models.py              # SQLAlchemy models (curated)
│   │   └── queries.py            # queries parametrizadas das métricas (P1, whitelist P5)
│   ├── agent/
│   │   ├── graph.py               # definição do grafo LangGraph (orquestrador)
│   │   ├── state.py               # estado tipado do grafo
│   │   ├── tools/
│   │   │   ├── metrics_tool.py    # chama db.queries (determinístico)
│   │   │   ├── chart_tool.py      # gera os 2 gráficos
│   │   │   └── news_tool.py       # busca Tavily com atribuição de fonte
│   │   ├── rag.py                 # RAG efêmero: embeddings + InMemoryVectorStore + retrieve top-k
│   │   ├── llm.py                 # camada provider-agnostic: chat + embeddings (P8)
│   │   └── prompts.py             # system prompt + guardrails de saída (P5)
│   ├── governance/
│   │   └── audit.py               # logging estruturado de decisões (P2)
│   ├── report/
│   │   ├── composer.py            # monta o relatório (métricas+gráficos+comentário+fontes)
│   │   └── pdf.py                 # render do PDF
│   └── api/
│       ├── main.py                # FastAPI app
│       ├── security.py            # middleware: API key + rate limit + CORS (P5, guardrail HTTP)
│       └── routes/                # /reports, /reports/{id}/pdf, /metrics, /data, /audit
├── app_streamlit.py               # cliente Streamlit que consome a API
├── tests/
├── pyproject.toml
├── requirements.txt               # dependências de runtime (imagem leve)
├── Dockerfile                     # multi-stage, python:slim, não-root
├── .dockerignore                  # contexto de build enxuto
├── docker-compose.yml             # db + api + streamlit (paridade local c/ Railway)
├── railway.json / Procfile        # config de deploy
├── .env.example
└── README.md                      # documentação principal (entrega)
```

## Convenções

- Uma responsabilidade por módulo; funções com type hints e docstring curta.
- Toda query ao banco passa por `src/db/queries.py` (nenhum SQL espalhado).
- Toda chamada de tool e LLM passa pelo `governance/audit.py`.
- Config só via `src/config.py`; nada de `os.getenv` espalhado.
