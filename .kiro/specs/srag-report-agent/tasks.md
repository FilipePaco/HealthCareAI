# Tasks — SRAG Report Agent

> Plano de implementação faseado para 5 dias. Cada task referencia os requisitos (Rx.y) que satisfaz.
> Marque `[x]` conforme concluir. Ordem pensada para ter algo demonstrável cedo (P: feito > perfeito).

## Fase 0 — Fundação (D1, manhã)
- [x] T0.1 — `pyproject.toml`, Ruff, pytest, estrutura de pastas de `structure.md`.
- [x] T0.2 — `src/config.py` (Pydantic Settings) lendo o contrato de env de `tech.md`. (R7.3)
- [x] T0.3 — `.env.example` (+ `.env` local gitignored) com o contrato de variáveis.
- [ ] T0.4 — Provisionar Postgres no Railway; validar `DATABASE_URL` local via túnel/instância. (R9.1)
- [ ] T0.5 — `Dockerfile` multi-stage + `.dockerignore` + `docker-compose.yml`; validar build leve e
  `docker compose up` (db + api + streamlit). (decisão §16)

## Fase 1 — Dados / ETL (D1 tarde – D2)
- [x] T1.1 — `etl/download.py` baixa o CSV real do DATASUS (2024, 194MB) + ETL em chunks; 267.692
  linhas carregadas. Dicionário e colunas mapeados em `data-and-metrics.md`. (R1.1)
- [x] T1.2 — `etl/clean.py`: seleção de colunas, parsing de datas, regras de ausência/inválidos
  documentadas, **remoção de identificadores**. (R1.2, R1.3, R1.4)
- [x] T1.3 — `db/models.py` + `etl/load.py`: carga idempotente em `srag_cases` + views diária/mensal. (R1.5)
- [x] T1.4 — Testes da ETL com linhas sujas sintéticas (8 casos, `tests/test_clean.py` + `TEST_PLAN.md`). (estratégia de testes §5)

## Fase 2 — Métricas e gráficos determinísticos (D2 – D3 manhã)
- [x] T2.1 — `db/queries.py`: 4 queries parametrizadas (aumento, mortalidade, UTI, vacinação) +
  whitelist + séries diária/mensal. (R2.1–R2.5, R7.1)
- [x] T2.2 — Testes das métricas com dados sintéticos de resultado conhecido (integração c/ Postgres). (R2.5)
- [x] T2.3 — Caso "sem dados" → nulo explícito (sem divisão por zero). (R2.6)
- [x] T2.4 — `agent/tools/chart_tool.py`: gráfico diário 30d e mensal 12m (densificação + PNG). (R3.1–R3.3)

## Fase 3 — Notícias + governança (D3)
- [x] T3.1 — `agent/tools/news_tool.py` (Tavily) com fonte/data e janela de recência. (R4.1–R4.4)
- [x] T3.2 — `agent/rag.py`: embeddings + `InMemoryVectorStore` + retrieve top-k (RAG efêmero). (R4.6)
- [x] T3.3 — `governance/audit.py`: logging estruturado de tools e LLM + tabela `audit_log`. (R6.1, R6.2)

## Fase 4 — Agente orquestrador (D3 tarde – D4)
- [x] T4.1 — `agent/llm.py` provider-agnostic (`init_chat_model` + embeddings). (P8/ADR-04)
- [x] T4.2 — `agent/state.py` + `agent/graph.py`: nós gather_metrics → news(+RAG) → compose;
  agência do LLM ao formular os termos de busca no nó de notícias. (R5.1, R4.5)
- [x] T4.3 — `agent/prompts.py` + `report/composer.py`: explicação **por métrica** + síntese, com
  **grounding** e disclaimer. (R5.2–R5.6)
- [x] T4.4 — Teste de grounding (fonte fora das notícias é descartada). (R5.4)

## Fase 5 — API + interface (D4)
- [x] T5.1 — `api/main.py` + `POST /reports` (roda o agente: comentário + fontes) + `/charts/*.png`.
  `GET /reports/{id}` com persistência do relatório fica como opcional (o trilho vai por `/audit/{id}`). (R8.1)
- [x] T5.2 — `report/pdf.py` (ReportLab) + `GET /reports/{id}` + `GET /reports/{id}/pdf` + persistência
  (`db/reports_store.py`). (R8.1, R8.2)
- [x] T5.3 — `GET /metrics`, `GET /data/daily`, `GET /data/monthly`, `GET /audit/{id}`. (R8.3, R6.3)
- [x] T5.5 — `api/security.py`: middleware API key (`X-API-Key`) + rate limiting (slowapi) + CORS. (R7.4–R7.7)
- [x] T5.4 — `app_streamlit.py` consumindo a API (botão gerar → métricas + gráficos + comentários + PDF). (R8.4)
- [x] T5.6 — `etl/seed.py`: dados sintéticos para usar/testar sem o CSV real. (apoio)

## Fase 7 — Agência real + observabilidade de custo (evolução)
- [x] T7.1 — `agent/news_agent.py`: laço de **tool-calling** (`bind_tools` → `buscar_noticias`), o LLM
  decide refinar/repetir a busca até `NEWS_AGENT_MAX_ITERS`; cada iteração auditada; fallback
  determinístico se o provedor não suportar tools. (R4.5, R4.7, R4.8 / ADR-11)
- [x] T7.2 — `governance/usage.py`: `UsageTracker` (tokens de LLM via `usage_metadata` + buscas Tavily)
  + custo estimado por tarifas de `config.py`. (R10.1, R10.2 / ADR-12)
- [x] T7.3 — Integrar uso ao relatório/auditoria e expor `GET /usage` (totais + últimos). Composer com
  `include_raw` para capturar tokens. (R10.3)
- [x] T7.4 — Streamlit mostra uso e custo estimado do relatório gerado. (R10.3)
- [x] T7.5 — Testes: laço de tool-calling (com fake LLM), `UsageTracker` (cálculo/custo), `GET /usage`;
  documentados em `TEST_PLAN.md` antes. (R4.x, R10.x)

## Fase 6 — Deploy + entrega (D5)
- [ ] T6.1 — Deploy no Railway via **Dockerfile** (build da imagem) + Postgres gerenciado; rodar ETL
  no ambiente. (R9.1, §16)
- [ ] T6.2 — **Diagrama conceitual** (Mermaid → PDF) em `docs/architecture/` (exigido na entrega).
- [ ] T6.3 — README final: arquitetura, decisões, governança, guardrails, dados sensíveis, como rodar.
- [ ] T6.4 — Revisão de clean code (Ruff), remoção de segredos, repositório público.

## Fase 8 — Auditoria em duas camadas + tracing Langfuse (ADR-13)

> Ordem pensada para que cada task entregue valor sozinha. T8.1–T8.3 valem mesmo que o Langfuse
> nunca suba; T8.4–T8.7 são a camada 2. Nenhuma delas altera o resultado do relatório.

### Camada 1 — endurecer o trilho que já existe
- [ ] T8.1 — `governance/audit.py`: evento **tipado** (`StrEnum` + dataclass com `node`, `status`,
  `duration_ms`, `parent_id`) e **escrita em lote** (buffer + `INSERT` múltiplo no fim, com flush em
  exceção). Substitui a transação-por-evento de hoje. (R6.5)
- [ ] T8.2 — Context manager `trail.span(...)` que cronometra e captura exceção automaticamente;
  migrar os `record(...".error")` manuais de `graph.py` e `news_agent.py` para ele. Aproveita
  `record_call`, hoje código morto. (R6.5)
- [ ] T8.3 — Registrar **prompt/resposta do LLM** (truncados + hash) e a **proveniência** (git SHA,
  provedor/modelo, versão dos prompts, referência da carga da ETL). Fecha o gap do P2. (R6.4, R6.6)
- [ ] T8.4 — Retenção e imutabilidade: `AUDIT_RETENTION_DAYS` na config, índice em `ts`, rotina de
  purga e `REVOKE UPDATE, DELETE` para o usuário da aplicação. (R6.7)
- [ ] T8.5 — Gerar `docs/auditoria.md` **a partir do enum** de eventos (hoje a doc já divergiu do
  código: descreve `formulate_query`/`gather_news`, que não são mais emitidos). (R6.3)

### Pré-requisitos de cobertura (valem para as duas camadas)
- [x] T8.6 — `news_agent.py`: invocar `buscar_noticias.invoke({"query": ...}, config=config)` em vez de
  chamar `search_news` diretamente — a tool ligada por `bind_tools` nunca é executada de fato hoje,
  então a busca não aparece como span. (R11.4)
- [x] T8.7 — `rag.py`: instrumentar embeddings (retrieval como runnable **ou** instrumentação OTel) e
  **contabilizá-los** no `UsageTracker`; registrar modelo e tarifa efetivos no `usage`. Corrige a
  subestimação atual do custo. (R10.4, R10.5, R11.5)

### Camada 2 — Langfuse
- [x] T8.8 — `governance/tracing.py`: `get_callbacks(report_id)` devolvendo `[]` quando desligado ou
  sem credenciais; nenhum outro módulo importa `langfuse`. Config nova em `config.py`
  (`TRACING_ENABLED`, `LANGFUSE_*`, `LANGFUSE_SAMPLE_RATE`). (R11.1, R11.3, R11.8)
- [x] T8.9 — Ligar no `graph.py`: `invoke(..., config={"callbacks": ...})`, com `report_id` como
  identificador do trace e tags de ambiente/versão. (R11.2, R11.6)
- [x] T8.10 — `requirements-obs.txt` (extras opcionais) + `ARG INSTALL_OBS` no Dockerfile e repasse das
  variáveis `TRACING_ENABLED`/`LANGFUSE_*` no `docker-compose.yml`, para que os extras entrem só quando
  o tracing for usado — a imagem base continua enxuta (§16/§17). (R11.1)
- [ ] T8.11 — Espelhar na camada 2 os **eventos de decisão** (`stop`, `max_iters`, `fallback`,
  `selected`) como eventos do trace: instrumentação automática captura chamadas, não intenções. (ADR-13)
- [ ] T8.12 — *(ação manual do dev)* Criar projeto no **Langfuse Cloud** (tier gratuito), gerar o par
  de chaves e preencher `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` + `TRACING_ENABLED=true` no `.env`
  e no service `api` do Railway. Passo a passo já escrito em `DEPLOY.md`. (R9.1)
- [x] T8.13 — Testes da camada 2: `tracing` inativo sem credenciais/SDK, `flush` silencioso, `report_id`
  como trace id, e embeddings entrando no `UsageTracker` (`tests/test_tracing.py`,
  `tests/test_rag_usage.py`). Os testes de evento tipado/lote acompanham T8.1. (R11.3, R10.5)

## Riscos / pontos de atenção
- **Qualidade dos dados DATASUS:** maior fonte de incerteza; reservar buffer na Fase 1.
- **Definição exata das métricas:** confirmar denominadores (ex.: mortalidade sobre casos vs sobre
  internados) contra o dicionário — decisão a documentar no README.
- **Free tier do LLM:** monitorar limites do Gemini; abstração permite trocar se estourar.
- **Volume (165k linhas):** usar views/índices; não carregar tudo em memória no runtime.
- **Teto do tier gratuito do Langfuse:** 50k units/mês e 30 dias de retenção. Folgado para a PoC
  (~2.000 relatórios/mês), mas se o volume subir, o tracing simplesmente para de ingerir — sem
  cobrança surpresa e **sem afetar a camada 1**. Acompanhar o consumo na UI (ADR-13).
- **Self-host descartado por custo:** ~6 services e US$ 30–40/mês no Railway, contra ~US$ 10 da
  aplicação inteira. Reavaliar só se surgir exigência de perímetro ou retenção longa — a migração é
  trocar `LANGFUSE_HOST`.
