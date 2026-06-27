# CLAUDE.md — Guia para agentes de código neste repositório

Contexto e regras para qualquer sessão de IA que for **implementar** este projeto. A especificação
(SDD) é a fonte da verdade; este arquivo resume o essencial e aponta para ela.

## O que é o projeto
PoC de IA Generativa para a Indicium HealthCare: um **agente orquestrador** que consulta dados reais
de SRAG (Open DATASUS) + notícias em tempo real e gera um **relatório auditável** com 4 métricas, 2
gráficos e comentários embasados. Deploy no Railway. **É uma PoC; o conteúdo não é orientação médica.**

## Fonte da verdade (leia antes de codar)
- `.kiro/steering/constitution.md` — **princípios invioláveis** (P1–P8). Respeite-os sempre.
- `.kiro/steering/tech.md` — stack e contrato de variáveis de ambiente.
- `.kiro/steering/structure.md` — estrutura-alvo de pastas e convenções.
- `.kiro/specs/srag-report-agent/requirements.md` — requisitos (EARS).
- `.kiro/specs/srag-report-agent/design.md` — arquitetura + ADRs.
- `.kiro/specs/srag-report-agent/data-and-metrics.md` — **definição exata das métricas e colunas**.
- `.kiro/specs/srag-report-agent/tasks.md` — plano de implementação (siga a ordem).
- `docs/decisoes-arquiteturais.md` — justificativa detalhada de cada decisão.

## Stack
Python 3.11+ · **LangGraph** (orquestração) · **Gemini 2.5 Flash** via `init_chat_model`
(provider-agnostic) · **PostgreSQL** (Railway) + SQLAlchemy · **FastAPI** (API-first) · **Streamlit**
(cliente da API) · **Tavily** (notícias) · **RAG efêmero** (`InMemoryVectorStore`) · Matplotlib ·
ReportLab (PDF) · Docker multi-stage (`python:3.11-slim`).

## Regras de ouro (derivadas da constituição)
- **Métricas são determinísticas.** O LLM NUNCA calcula nem escreve SQL. Use as queries
  parametrizadas de `src/db/queries.py` (whitelist). (P1, P5)
- **Agência só no nó de notícias.** O LLM formula/refina termos de busca; o resto é determinístico. (ADR-09)
- **Só agregados saem do banco.** Microdados nunca vão para a API, para o LLM nem para logs. (P4)
- **Tudo é auditável.** Toda chamada de tool/LLM passa por `src/governance/audit.py`. (P2)
- **Grounding obrigatório.** Toda afirmação cita métrica e/ou notícia (URL+data); senão é descartada. (P3)
- **Guardrails de fronteira.** SQL whitelist; recência de notícias; saída do LLM em schema + disclaimer;
  API com API key + rate limit + CORS. (P5)
- **Segredos só via env**, nunca em código ou logs. (P5)
- **Config centralizada** em `src/config.py` (Pydantic Settings). Nada de `os.getenv` espalhado; sem
  números mágicos (janelas/limiares vêm da config). (P7)
- **Imagem leve.** Sem dependências nativas pesadas (por isso ReportLab, não WeasyPrint; sem
  faiss/chroma). Não adicione libs sem necessidade. (§16, §17)

## Fora de escopo (não implemente)
- Autenticação de usuários (login/cadastro/roles) — só segurança mínima de API. (ADR-10)
- Front-end customizado — apenas os endpoints ficam prontos.
- Streaming de dados do DATASUS — carga é batch.
- text-to-SQL / agente ReAct de tools livres.

## Comandos (alvo — ainda não implementados)
```bash
# Ambiente local completo (db + api + streamlit)
docker compose up --build

# Sem Docker
pip install -r requirements.txt
python -m src.etl.load          # ETL: baixa/limpa/carrega o CSV no Postgres
uvicorn src.api.main:app --reload
streamlit run app_streamlit.py

# Qualidade
ruff check .
pytest
```

## Convenções
- Type hints em tudo; funções pequenas, responsabilidade única; docstring curta.
- Contratos Pydantic nas fronteiras (API e tools).
- Todo acesso ao banco passa por `src/db/queries.py`; toda decisão de agente por `governance/audit.py`.
- Ao concluir uma task, marque `[x]` em `tasks.md`.
