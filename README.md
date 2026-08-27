# HealthCareAI — SRAG Report Agent

PoC de IA Generativa para a **Indicium HealthCare Inc.**: um agente orquestrador que consulta dados
reais de internações por SRAG (Open DATASUS) e notícias em tempo real para gerar, de forma
automatizada e **auditável**, um relatório com métricas, gráficos e comentários embasados.

> ⚠️ Prova de Conceito de caráter educacional. O conteúdo gerado **não constitui orientação médica**.

**Status:** funcional de ponta a ponta — ETL com dados reais do DATASUS, 4 métricas determinísticas,
2 gráficos, agente LangGraph com tool-calling e RAG, trilho de auditoria, API com guardrails,
Streamlit e export em PDF. **67 testes**, lint limpo.
Deploy no Railway em [`DEPLOY.md`](DEPLOY.md) · limitações conhecidas [no fim deste documento](#limitações-conhecidas).

---

## Sumário

- [Como rodar](#como-rodar) · [O que o relatório entrega](#o-que-o-relatório-entrega) · [API](#api)
- [Arquitetura](#arquitetura) · [Governança e auditoria](#governança-e-auditoria) · [Guardrails](#guardrails) · [Dados sensíveis](#dados-sensíveis)
- [Observabilidade de custo](#observabilidade-de-custo) · [Tracing opcional](#tracing-opcional-langfuse) · [Testes](#testes)
- [Especificação (SDD)](#especificação-spec-driven-development) · [Limitações conhecidas](#limitações-conhecidas)

---

## Como rodar

Copie `.env.example` para `.env` e preencha `GOOGLE_API_KEY` e `TAVILY_API_KEY`. O `.env` nunca é
versionado.

### Com Docker (recomendado)

```bash
docker compose up --build                                    # db + api + streamlit
docker compose exec api python -m src.etl.seed --rows 5000   # dados sintéticos, noutro terminal
```

- **Streamlit:** http://localhost:8501 → botão *Gerar relatório*
- **API (Swagger):** http://localhost:8000/docs → *Authorize* com a sua `API_KEY`

> **Atenção à porta do banco.** O `docker-compose.yml` expõe o Postgres em **`localhost:5433`**
> (não 5432), para não conflitar com um Postgres instalado na máquina. Entre containers o host é
> `db:5432`. Se for rodar a API ou os testes fora do Docker contra esse banco, use
> `DATABASE_URL=postgresql+psycopg2://srag:srag@localhost:5433/srag`.

Para usar **dados reais** do DATASUS (SRAG 2024, ~268 mil casos) no lugar do seed:

```bash
docker compose exec api python -m src.etl.load --year 2024   # baixa ~194 MB e carrega em chunks
```

### Sem Docker (venv)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# suba um Postgres e aponte DATABASE_URL no .env para ele
python -m src.etl.seed --rows 5000
uvicorn src.api.main:app --reload      # API  em :8000
streamlit run app_streamlit.py         # UI   em :8501
```

O Streamlit é apenas um cliente HTTP da API: ele lê `API_BASE_URL` e `API_KEY` do ambiente e não
toca no banco.

---

## O que o relatório entrega

**Quatro métricas**, calculadas por SQL parametrizado — o LLM nunca as produz nem escreve a query
(P1). Cada métrica devolve valor, numerador, denominador e uma nota com a definição usada; quando
não há dados suficientes, o valor vem `null` explícito, em vez de um número inventado.

| Métrica | Definição exata | Ressalva importante |
|---|---|---|
| `taxa_aumento_casos` | Variação % entre duas janelas *half-open* consecutivas de 14 dias (`REPORT_INCREASE_WINDOW_DAYS`), ancoradas na data de referência | `null` se a janela anterior não tiver casos |
| `taxa_mortalidade` | CFR: óbitos ÷ **desfechos conhecidos** (cura ou óbito) | Não é sobre todos os casos — casos em aberto ficam fora do denominador |
| `taxa_ocupacao_uti` | Internados que precisaram de UTI ÷ total de internados | **Não é ocupação de leitos.** É a proporção de internados que necessitou UTI |
| `taxa_vacinacao` | Vacinados ÷ casos com status vacinal conhecido | É vacinação **COVID entre os casos de SRAG**, não cobertura da população geral |

As duas últimas ressalvas importam: os nomes das métricas vêm do enunciado do desafio, mas o dado do
DATASUS não sustenta a leitura literal. A definição real está no `note` de cada métrica, aparece no
JSON do relatório e é a que o LLM recebe para comentar.

**Dois gráficos:** casos diários dos últimos 30 dias e mensais dos últimos 12 meses, derivados das
mesmas views das métricas.

**Comentários do agente:** uma explicação por métrica mais uma síntese geral, cada afirmação ancorada
no valor calculado e/ou em notícia recuperada, **com a URL citada**. Fonte que não esteja entre as
notícias recuperadas é descartada em código, não por confiança no modelo.

Definição completa das colunas e das métricas:
[`data-and-metrics.md`](.kiro/specs/srag-report-agent/data-and-metrics.md).

---

## API

Todos os endpoints, exceto `/health`, exigem o header `X-API-Key`.

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/health` | Liveness (sem autenticação) |
| `POST` | `/reports` | **Roda o agente** e devolve o relatório completo em JSON |
| `GET` | `/reports/{id}` | Recupera um relatório já gerado |
| `GET` | `/reports/{id}/pdf` | Exporta o relatório em PDF |
| `GET` | `/audit/{id}` | **Trilho de auditoria** daquele relatório |
| `GET` | `/usage` | Uso e custo estimado, agregado e por relatório |
| `GET` | `/metrics` | As 4 métricas com numerador/denominador |
| `GET` | `/data/daily` · `/data/monthly` | Séries agregadas, para um front-end futuro |
| `GET` | `/charts/daily.png` · `/charts/monthly.png` | Gráficos renderizados |

```bash
KEY=$(grep '^API_KEY=' .env | cut -d= -f2-)
RID=$(curl -s -X POST localhost:8000/reports -H "X-API-Key: $KEY" | jq -r .report_id)
curl -s localhost:8000/audit/$RID -H "X-API-Key: $KEY" | jq
```

> `POST /reports` é **síncrono** e leva ~15 s: roda o laço de notícias, os embeddings e a composição.
> Ver [limitações](#limitações-conhecidas).

---

## Arquitetura

API-first e agente-cêntrica, com separação rígida entre preparação de dados e runtime.

- **ETL offline** (`src/etl/`) — baixa, limpa, seleciona colunas e anonimiza o CSV do DATASUS,
  carregando no Postgres de forma idempotente. Separado do runtime (P6).
- **Agente LangGraph** (`src/agent/`) — grafo de três nós: `metrics` → `news` → `compose`.
  As métricas são determinísticas; **a agência do LLM vive só no nó de notícias**, onde ele formula
  a query, lê os resultados e decide se refina e busca de novo, até `NEWS_AGENT_MAX_ITERS`
  (ADR-09/ADR-11). Os gráficos são derivados fora do grafo, direto das views.
- **RAG efêmero** (`src/agent/rag.py`) — as notícias acumuladas são embeddadas num
  `InMemoryVectorStore` reconstruído a cada requisição e descartado em seguida. Sem vector DB
  persistente: notícia é efêmera (ADR-08).
- **LLM provider-agnostic** (`src/agent/llm.py`) — `init_chat_model`; trocar Gemini ↔ OpenAI ↔
  Anthropic é mudar `LLM_PROVIDER`/`LLM_MODEL` (P8).
- **API FastAPI** — o relatório é um recurso. **Streamlit é só um cliente** desses endpoints,
  exatamente a fronteira que um front-end futuro usaria.

Diagrama conceitual: [`docs/architecture/architecture.md`](docs/architecture/architecture.md) ·
arquitetura completa e ADRs: [`design.md`](.kiro/specs/srag-report-agent/design.md).

---

## Governança e auditoria

A auditoria roda em **duas camadas**, que respondem a perguntas diferentes (ADR-13):

| | **Camada 1** — `audit_log` | **Camada 2** — Langfuse |
|---|---|---|
| Responde a | auditor / avaliador | quem está desenvolvendo |
| Registra | decisões e resultado | mecânica da execução |
| Onde vive | seu Postgres | serviço externo |
| Pode ser desligada? | **não** | sim, e é o default |

A **camada 1 é o registro de conformidade**: cada geração grava, evento a evento, as métricas
calculadas, cada iteração do laço de tool-calling (com a query que o modelo escolheu e quantos
resultados vieram), a decisão de parar, as notícias selecionadas, o comentário composto e o consumo.
Não depende de nenhum serviço externo estar no ar.

```
gather_metrics         {'taxa_mortalidade': 25.39, 'taxa_ocupacao_uti': 33.16, ...}
news_agent.tool_call   query='tendência casos SRAG Brasil'      -> 6 artigos
news_agent.tool_call   query='mortalidade SRAG Brasil'          -> 6 artigos
news_agent.tool_call   query='ocupação leitos UTI SRAG Brasil'  -> 6 artigos
news_agent.tool_call   query='vacinação gripe COVID Brasil'     -> 6 artigos
news_agent.stop        modelo encerrou a busca
news_agent.selected    6 selecionadas p/ o RAG
compose                4 comentários, 6 fontes
usage                  US$ 0.0337 | 6449 tokens
```

Esse trilho é o que permite reconstruir **por que** o agente disse o que disse. Como acessá-lo e o
que cada evento significa: [`docs/auditoria.md`](docs/auditoria.md).

---

## Guardrails

Cada fronteira de confiança tem um controle explícito (P5):

| Fronteira | Controle |
|---|---|
| Banco | Whitelist de queries parametrizadas em `db/queries.py`; nome fora da whitelist é rejeitado. Nenhum SQL livre, nenhum text-to-SQL |
| LLM → números | O modelo **nunca** calcula métrica; ele recebe valores já computados e apenas interpreta |
| LLM → saída | Saída estruturada por schema Pydantic + disclaimer obrigatório |
| LLM → fontes | Grounding forçado em código: URL citada que não esteja entre as notícias recuperadas é removida |
| Internet | Busca com janela de recência, atribuição de fonte e limite de iterações do laço |
| HTTP | API key (`X-API-Key`), rate limiting (`slowapi`) e CORS restrito |
| Segredos | Só por variável de ambiente; nunca em código, log ou trilho |

Falha de LLM ou de busca **degrada, não quebra**: o nó de notícias cai para uma busca determinística
e, no limite, o relatório sai com métricas e gráficos válidos sinalizando a ausência de contexto.

---

## Dados sensíveis

- **Minimização na origem:** a ETL seleciona apenas as colunas necessárias às métricas e descarta
  identificadores diretos e quase-identificadores antes da carga.
- **Só agregados saem do banco.** Microdados nunca chegam à API, ao LLM, ao PDF ou ao trilho.
- Os prompts são montados a partir de valores agregados e trechos de notícia pública — por
  construção não há microdado a vazar, inclusive para o tracing externo.

---

## Observabilidade de custo

Cada relatório mede e expõe o que consumiu dos três recursos pagos (P9):

```json
{ "llm_calls": 3, "input_tokens": 4991, "output_tokens": 1720,
  "embedding_calls": 2, "embedding_tokens": 5411, "tavily_searches": 4,
  "estimated_cost_usd": 0.033999, "estimate": true,
  "provider": "google_genai", "model": "gemini-2.5-flash-lite",
  "rates_usd": { "llm_input_per_1m": 0.1, "llm_output_per_1m": 0.4,
                 "embedding_per_1m": 0.15, "tavily_per_search": 0.008 } }
```

O payload registra **o modelo e as tarifas aplicadas** junto do valor: sem isso, comparar relatórios
gerados com modelos diferentes daria conclusão errada. É **estimativa** a partir de tarifas
configuráveis, não fatura — e vem rotulada como tal. Agregado em `GET /usage`.

Nesse exemplo, as buscas Tavily respondem por ~94% do custo; o LLM, por ~3%.

---

## Tracing opcional (Langfuse)

A camada 2 dá o que o trilho ainda não dá: prompt e resposta completos, latência por nó e tokens por
chamada. **Desligada por default** — sem as variáveis, a aplicação roda idêntica.

```bash
pip install -r requirements-obs.txt     # no venv
# .env:  TRACING_ENABLED=true  +  LANGFUSE_PUBLIC_KEY  +  LANGFUSE_SECRET_KEY
```

> **No Docker/Railway**, o pacote não entra na imagem base: construa com
> `--build-arg INSTALL_OBS=true` (o `docker-compose.yml` já faz isso). Sem o pacote, o tracing
> degrada **em silêncio** — que é o contrato, mas o trace nunca aparece.

O `report_id` é usado como identificador do trace, então o mesmo relatório é localizável nas duas
camadas. Se o Langfuse estiver fora do ar, sem credenciais ou desligado, o relatório é gerado
normalmente e o `audit_log` segue completo: **tracing nunca é caminho crítico**.

---

## Testes

```bash
pytest                    # 67 testes
ruff check .              # lint
```

**67 testes.** Os 18 de integração pulam automaticamente sem Postgres acessível; os demais são puros
(sem rede, sem banco). Testes que consomem LLM/Tavily reais pulam sem chave, e pulam também em
erro `429`/`503` — o free tier do Gemini é limitado a 20 requisições por dia por modelo.

Duas pegadinhas ao rodar localmente:

- **Aponte para a porta certa.** Contra o banco do compose:
  `DATABASE_URL=postgresql+psycopg2://srag:srag@localhost:5433/srag pytest`. Sem isso os 18 de
  integração pulam em silêncio e parecem "passar".
- **`pytest` limpa a tabela `srag_cases`.** Rode o seed de novo antes de demonstrar a UI.

Plano de testes e rastreabilidade requisito ↔ teste: [`tests/TEST_PLAN.md`](tests/TEST_PLAN.md).

---

## Especificação (Spec-Driven Development)

Metodologia: estrutura **Kiro** + **constitution** (conceito do GitHub Spec Kit) para governança.

| Documento | Conteúdo |
|---|---|
| [`constitution.md`](.kiro/steering/constitution.md) | Princípios invioláveis (P1–P9) |
| [`tech.md`](.kiro/steering/tech.md) | Stack e contrato de variáveis de ambiente |
| [`structure.md`](.kiro/steering/structure.md) | Estrutura do repositório e convenções |
| [`requirements.md`](.kiro/specs/srag-report-agent/requirements.md) | Requisitos em EARS |
| [`design.md`](.kiro/specs/srag-report-agent/design.md) | Arquitetura + 13 ADRs |
| [`data-and-metrics.md`](.kiro/specs/srag-report-agent/data-and-metrics.md) | Colunas DATASUS + definição das métricas |
| [`tasks.md`](.kiro/specs/srag-report-agent/tasks.md) | Plano de implementação e pendências |

### Onde cada critério de avaliação é endereçado

| Critério | Onde |
|---|---|
| Escolha da arquitetura | `design.md` §1–3 + ADR-01 a ADR-13 |
| Governança e transparência | P2 · `governance/audit.py` · `GET /audit/{id}` · [`docs/auditoria.md`](docs/auditoria.md) |
| Guardrails | P5 · whitelist SQL · grounding forçado · schema + disclaimer · API key/rate limit/CORS |
| Uso de tools | Tool-calling real no nó de notícias (ADR-11) + tools determinísticas de métrica e gráfico |
| Tratamento de dados sensíveis | P4 · anonimização na ETL · só agregados na API, no LLM e no trilho |
| Clean code | Ruff · type hints · Pydantic nas fronteiras · 67 testes |

---

## Limitações conhecidas

Registradas honestamente; as pendências estão detalhadas em
[`tasks.md`](.kiro/specs/srag-report-agent/tasks.md).

- **`POST /reports` é síncrono** (~15 s). Num deploy atrás de proxy isso flerta com timeout, e a UI
  fica sem feedback de progresso. O padrão adequado seria `202 Accepted` + polling.
- **O trilho não registra prompt, resposta nem duração.** Você sabe *o que* o agente decidiu, não
  quanto tempo levou nem o que exatamente foi enviado ao modelo — hoje só o tracing mostra isso.
  Tasks T8.1–T8.3.
- **`audit_log` não tem retenção nem imutabilidade.** Sem prazo de purga e sem `REVOKE` de
  `UPDATE`/`DELETE`. Task T8.4.
- **Sem CI.** `ruff` e `pytest` dependem de alguém lembrar de rodar.
- **Dependências sem lockfile** (`>=`), o que enfraquece a reprodutibilidade prometida em P6.
- **Sem retry/backoff nas chamadas ao LLM**: um `429` transitório derruba direto para o fallback.
- **Sem verificação numérica do comentário** — o grounding valida a fonte citada, não se o número
  mencionado no texto bate com a métrica.
- **Escopo deliberadamente fora:** autenticação de usuários, front-end customizado, streaming do
  DATASUS e alta disponibilidade (ADR-10 e §"Fora de escopo" dos requisitos).
