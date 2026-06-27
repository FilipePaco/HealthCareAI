# Tasks — SRAG Report Agent

> Plano de implementação faseado para 5 dias. Cada task referencia os requisitos (Rx.y) que satisfaz.
> Marque `[x]` conforme concluir. Ordem pensada para ter algo demonstrável cedo (P: feito > perfeito).

## Fase 0 — Fundação (D1, manhã)
- [ ] T0.1 — `pyproject.toml`, Ruff, pytest, estrutura de pastas de `structure.md`.
- [ ] T0.2 — `src/config.py` (Pydantic Settings) lendo o contrato de env de `tech.md`. (R7.3)
- [ ] T0.3 — `.env.example` + README inicial com instruções de setup.
- [ ] T0.4 — Provisionar Postgres no Railway; validar `DATABASE_URL` local via túnel/instância. (R9.1)
- [ ] T0.5 — `Dockerfile` multi-stage + `.dockerignore` + `docker-compose.yml`; validar build leve e
  `docker compose up` (db + api + streamlit). (decisão §16)

## Fase 1 — Dados / ETL (D1 tarde – D2)
- [ ] T1.1 — Baixar CSV do DATASUS e o **dicionário de dados**; mapear colunas das 4 métricas. (R1.1)
- [ ] T1.2 — `etl/clean.py`: seleção de colunas, parsing de datas, regras de ausência/inválidos
  documentadas, **remoção de identificadores**. (R1.2, R1.3, R1.4)
- [ ] T1.3 — `db/models.py` + `etl/load.py`: carga idempotente em `srag_cases` + views diária/mensal. (R1.5)
- [ ] T1.4 — Testes da ETL com linhas sujas sintéticas. (estratégia de testes §5)

## Fase 2 — Métricas e gráficos determinísticos (D2 – D3 manhã)
- [ ] T2.1 — `db/queries.py`: 4 queries parametrizadas (aumento, mortalidade, UTI, vacinação) +
  whitelist. (R2.1–R2.5, R7.1)
- [ ] T2.2 — Testes das métricas com dados sintéticos de resultado conhecido. (R2.5)
- [ ] T2.3 — Caso "sem dados" → nulo explícito com justificativa. (R2.6)
- [ ] T2.4 — `agent/tools/chart_tool.py`: gráfico diário 30d e mensal 12m. (R3.1–R3.3)

## Fase 3 — Notícias + governança (D3)
- [ ] T3.1 — `agent/tools/news_tool.py` (Tavily) com fonte/data e janela de recência. (R4.1–R4.4)
- [ ] T3.2 — `agent/rag.py`: embeddings + `InMemoryVectorStore` + retrieve top-k (RAG efêmero). (R4.6)
- [ ] T3.3 — `governance/audit.py`: logging estruturado de tools e LLM + tabela `audit_log`. (R6.1, R6.2)

## Fase 4 — Agente orquestrador (D3 tarde – D4)
- [ ] T4.1 — `agent/llm.py` provider-agnostic (`init_chat_model`). (P8/ADR-04)
- [ ] T4.2 — `agent/state.py` + `agent/graph.py`: nós gather_metrics → charts → news(+RAG) → compose;
  agência do LLM ao formular/refinar termos de busca no nó de notícias. (R5.1, R4.5)
- [ ] T4.3 — `agent/prompts.py` + `report/composer.py`: explicação **por métrica** + síntese, com
  **grounding** e disclaimer. (R5.2–R5.6)
- [ ] T4.4 — Teste de grounding (afirmação sem fonte é descartada/marcada). (R5.4)

## Fase 5 — API + interface (D4)
- [ ] T5.1 — `api/main.py` + rotas `POST /reports`, `GET /reports/{id}`. (R8.1)
- [ ] T5.2 — `report/pdf.py` + `GET /reports/{id}/pdf`. (R8.2)
- [ ] T5.3 — `GET /metrics`, `GET /data/daily`, `GET /data/monthly`, `GET /audit/{id}`. (R8.3, R6.3)
- [ ] T5.5 — `api/security.py`: middleware API key (`X-API-Key`) + rate limiting (slowapi) + CORS. (R7.4–R7.7)
- [ ] T5.4 — `app_streamlit.py` consumindo a API (botão gerar → métricas + gráficos + comentários + PDF). (R8.4)

## Fase 6 — Deploy + entrega (D5)
- [ ] T6.1 — Deploy no Railway via **Dockerfile** (build da imagem) + Postgres gerenciado; rodar ETL
  no ambiente. (R9.1, §16)
- [ ] T6.2 — **Diagrama conceitual** (Mermaid → PDF) em `docs/architecture/` (exigido na entrega).
- [ ] T6.3 — README final: arquitetura, decisões, governança, guardrails, dados sensíveis, como rodar.
- [ ] T6.4 — Revisão de clean code (Ruff), remoção de segredos, repositório público.

## Riscos / pontos de atenção
- **Qualidade dos dados DATASUS:** maior fonte de incerteza; reservar buffer na Fase 1.
- **Definição exata das métricas:** confirmar denominadores (ex.: mortalidade sobre casos vs sobre
  internados) contra o dicionário — decisão a documentar no README.
- **Free tier do LLM:** monitorar limites do Gemini; abstração permite trocar se estourar.
- **Volume (165k linhas):** usar views/índices; não carregar tudo em memória no runtime.
