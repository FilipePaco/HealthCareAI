# Steering — Stack Tecnológica

Decisões de stack travadas para a PoC. Justificativas detalhadas estão em
`.kiro/specs/srag-report-agent/design.md` (seção "Decisões Arquiteturais").

| Camada | Escolha | Motivo curto |
|---|---|---|
| Linguagem | Python 3.11+ | Ecossistema GenAI; exigido no desafio |
| Orquestração do agente | **LangGraph** | Grafo de estado explícito → rastreabilidade/auditoria (P2) |
| Agência (notícias) | **LLM *tool-calling*** (`bind_tools`) em laço | O modelo decide chamar/refinar a busca `buscar_noticias` (ADR-11) |
| Observabilidade de custo | **`UsageTracker`** (interno) | Mede tokens de LLM + buscas Tavily e estima custo por relatório (P9/ADR-12) |
| LLM (default) | **Gemini 2.5 Flash-Lite** via `init_chat_model` | Free tier com cota diária maior que o 2.5-flash (que é 20 req/dia); abstraído (P8) |
| Banco de dados | **PostgreSQL** (Railway) | Tool SQL parametrizada; separa ETL de runtime (P6) |
| Busca de notícias | **Tavily** (tool) | API de busca desenhada para agentes, retorna fonte+data |
| Embeddings | **Gemini `gemini-embedding-001`** (via abstração) | RAG sobre notícias; mesmo provedor do chat |
| Vector store | **LangChain `InMemoryVectorStore`** | RAG efêmero por requisição; sem infra/peso extra |
| Backend/API | **FastAPI** | API-first; endpoints p/ relatório, PDF e exploração |
| Gráficos | **Matplotlib** (server-side) | Render determinístico p/ embutir no PDF e servir via API |
| Interface | **Streamlit** (cliente da API) | Demo rápida; consome os mesmos endpoints do front futuro |
| Validação/contratos | **Pydantic v2** | Schemas nas fronteiras (P7) |
| Segurança da API | **API key** (`X-API-Key`) + **slowapi** (rate limit) + **CORS** | Guardrail da fronteira HTTP; sem auth de usuários |
| Migrations/ORM | **SQLAlchemy** (+ Alembic opcional) | Acesso parametrizado e seguro ao Postgres |
| Containerização | **Docker** multi-stage (`python:3.11-slim`) | Imagem leve, sem libs nativas; não-root |
| PDF | **ReportLab** | Pure-Python, mantém a imagem enxuta (sem cairo/pango) |
| Deploy | **Railway** | Postgres + web service one-click; foco em PoC |
| Testes | **pytest** | Cobertura das tools determinísticas e da ETL |
| Lint/format | **Ruff** | Clean code automatizado |

## Variáveis de ambiente (contrato)
```
LLM_PROVIDER=google_genai        # google_genai | openai | anthropic
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=...               # ou OPENAI_API_KEY / ANTHROPIC_API_KEY
TAVILY_API_KEY=...
DATABASE_URL=postgresql://...    # injetada pelo Railway
API_KEY=...                      # segredo da fronteira HTTP (header X-API-Key)
CORS_ORIGINS=http://localhost:8501  # origens permitidas (CSV)
RATE_LIMIT=30/minute             # limite por cliente (slowapi)
REPORT_INCREASE_WINDOW_DAYS=14   # limiares parametrizados (P7)
NEWS_RECENCY_DAYS=30
NEWS_AGENT_MAX_ITERS=3           # nº máx. de iterações do laço de tool-calling de notícias (ADR-11)
NEWS_RETRIEVE_K=6                # top-k de notícias recuperadas pelo RAG (cobertura por métrica)
LLM_INPUT_COST_PER_1M=0.10       # tarifa estimada USD / 1M tokens de entrada (P9)
LLM_OUTPUT_COST_PER_1M=0.40      # tarifa estimada USD / 1M tokens de saída
TAVILY_COST_PER_SEARCH=0.008     # tarifa estimada USD / busca (free tier = 0)
```
