# HealthCareAI — SRAG Report Agent

PoC de IA Generativa para a **Indicium HealthCare Inc.**: um agente orquestrador que consulta dados
reais de internações por SRAG (Open DATASUS) e notícias em tempo real para gerar, de forma
automatizada e **auditável**, um relatório com métricas, gráficos e comentários embasados.

> ⚠️ Prova de Conceito de caráter educacional. O conteúdo gerado **não constitui orientação médica**.

## Status
🚧 **Fase de especificação (SDD).** O design está completo em `.kiro/`; a implementação segue o
`tasks.md`. Este README será expandido com instruções de execução conforme o código avança.

## Métricas e entregas do relatório
- Taxa de aumento de casos · taxa de mortalidade · taxa de ocupação de UTI · taxa de vacinação.
- Gráfico de casos diários (30 dias) e mensais (12 meses).
- Comentários do agente embasados em notícias, **com citação de fonte**.

## Arquitetura (resumo)
API-first e agente-cêntrica, com separação ETL ↔ runtime:

- **ETL offline** → limpa/seleciona/anonimiza o CSV do DATASUS e carrega no **PostgreSQL (Railway)**.
- **Agente LangGraph** → orquestra tools de métricas (SQL parametrizado, determinístico), gráficos e
  notícias (Tavily), e compõe comentários via **LLM provider-agnostic** (Gemini por padrão).
- **Governança** → toda decisão de agente/tool/LLM é registrada num trilho de auditoria.
- **API FastAPI** → relatório como recurso (JSON + export PDF) e endpoints de exploração de dados
  para um front-end futuro; **Streamlit** é apenas um cliente da API.

Diagrama conceitual: [`docs/architecture/architecture.md`](docs/architecture/architecture.md).

## Especificação (Spec-Driven Development)
Metodologia: estrutura **Kiro** + **constitution** (conceito do GitHub Spec Kit) para governança.

| Documento | Conteúdo |
|---|---|
| [`.kiro/steering/constitution.md`](.kiro/steering/constitution.md) | Princípios invioláveis (governança, guardrails, dados sensíveis) |
| [`.kiro/steering/tech.md`](.kiro/steering/tech.md) | Stack e contrato de variáveis de ambiente |
| [`.kiro/steering/structure.md`](.kiro/steering/structure.md) | Estrutura-alvo do repositório |
| [`.kiro/specs/srag-report-agent/requirements.md`](.kiro/specs/srag-report-agent/requirements.md) | Requisitos (EARS) |
| [`.kiro/specs/srag-report-agent/design.md`](.kiro/specs/srag-report-agent/design.md) | Arquitetura + decisões (ADRs) |
| [`.kiro/specs/srag-report-agent/data-and-metrics.md`](.kiro/specs/srag-report-agent/data-and-metrics.md) | Colunas DATASUS + definição exata das 4 métricas |
| [`.kiro/specs/srag-report-agent/tasks.md`](.kiro/specs/srag-report-agent/tasks.md) | Plano de implementação |
| [`docs/decisoes-arquiteturais.md`](docs/decisoes-arquiteturais.md) | Justificativa **detalhada** de cada decisão (incl. FastAPI vs Django, LLM, etc.) |

## Como esta solução endereça os critérios de avaliação
| Critério | Onde |
|---|---|
| Escolha da arquitetura | `design.md` (§1–3 + ADRs) |
| Governança e Transparência | `constitution.md` P2 · `governance/audit.py` · `GET /audit/:id` |
| Guardrails | `constitution.md` P5 · whitelist SQL · grounding · disclaimer · segurança da API (API key + rate limit + CORS) |
| Uso de Tools | métricas, gráficos, notícias (LangGraph) |
| Tratamento de Dados Sensíveis | `constitution.md` P4 · anonimização na ETL · só agregados |
| Clean Code | `structure.md` · Ruff · Pydantic · testes |
