# HealthCareAI — SRAG Report Agent

A generative-AI proof of concept: an orchestrating agent that queries real hospitalization data for
severe acute respiratory syndrome (SRAG, from Brazil's Open DATASUS) and live news, then produces an
automated, **auditable** report with metrics, charts and grounded commentary.

> ⚠️ Educational proof of concept. The generated content **is not medical advice**.

**Status:** working end to end. ETL on real DATASUS data, 4 deterministic metrics, 2 charts, a
LangGraph agent with tool calling and RAG, an audit trail, an API with guardrails, a Streamlit client
and PDF export. **67 tests**, clean lint.
Railway deployment in [`DEPLOY.md`](DEPLOY.md) · known limitations [at the end](#known-limitations).

## Highlights

- **The LLM never computes a number.** Metrics come from whitelisted, parameterized SQL; the model
  only interprets values it is given.
- **Agency where it is useful.** The model drives a real tool-calling loop over news search, with an
  iteration cap and a deterministic fallback.
- **Grounding enforced in code.** Any cited URL that is not among the retrieved articles is dropped.
- **Two-layer audit.** A compliance trail in Postgres that cannot be switched off, plus optional
  Langfuse tracing for developers.
- **Cost observability.** Every report records tokens, searches, the model and the rates used to
  estimate its cost.

---

## Contents

- [Running it](#running-it) · [What the report delivers](#what-the-report-delivers) · [API](#api)
- [Architecture](#architecture) · [Governance and audit](#governance-and-audit) · [Guardrails](#guardrails) · [Sensitive data](#sensitive-data)
- [Cost observability](#cost-observability) · [Optional tracing](#optional-tracing-langfuse) · [Tests](#tests)
- [Specification (SDD)](#specification-spec-driven-development) · [Known limitations](#known-limitations)

---

## Running it

Copy `.env.example` to `.env` and set `GOOGLE_API_KEY` and `TAVILY_API_KEY`. The `.env` file is
never committed.

### With Docker (recommended)

```bash
docker compose up --build                                    # db + api + streamlit
docker compose exec api python -m src.etl.seed --rows 5000   # synthetic data, in another terminal
```

- **Streamlit:** http://localhost:8501 → *Gerar relatório* (Generate report)
- **API (Swagger):** http://localhost:8000/docs → *Authorize* with your `API_KEY`

> **Database port.** `docker-compose.yml` exposes Postgres on **`localhost:5433`** (not 5432) to
> avoid clashing with a local Postgres. Between containers the host is `db:5432`. To run the API or
> tests outside Docker against that database, use
> `DATABASE_URL=postgresql+psycopg2://srag:srag@localhost:5433/srag`.

To use **real** DATASUS data (SRAG 2024, ~268k cases) instead of the seed:

```bash
docker compose exec api python -m src.etl.load --year 2024   # downloads ~194 MB, loads in chunks
```

### Without Docker (venv)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# start a Postgres and point DATABASE_URL in .env to it
python -m src.etl.seed --rows 5000
uvicorn src.api.main:app --reload      # API on :8000
streamlit run app_streamlit.py         # UI  on :8501
```

Streamlit is only an HTTP client of the API: it reads `API_BASE_URL` and `API_KEY` from the
environment and never touches the database.

---

## What the report delivers

**Four metrics**, computed by parameterized SQL. The LLM never produces them or writes the query
(P1). Each metric returns its value, numerator, denominator and a note with the definition used. When
there is not enough data the value is an explicit `null` rather than an invented number.

| Metric | Exact definition | Important caveat |
|---|---|---|
| `taxa_aumento_casos` (case growth) | % change between two consecutive half-open 14-day windows (`REPORT_INCREASE_WINDOW_DAYS`) anchored on the reference date | `null` if the earlier window has no cases |
| `taxa_mortalidade` (mortality) | CFR: deaths ÷ **known outcomes** (recovery or death) | Not over all cases; open cases are outside the denominator |
| `taxa_ocupacao_uti` (ICU) | Hospitalized patients who needed ICU ÷ all hospitalized | **Not bed occupancy.** It is the share of inpatients who needed ICU |
| `taxa_vacinacao` (vaccination) | Vaccinated ÷ cases with known vaccination status | COVID vaccination **among SRAG cases**, not population coverage |

The last two caveats matter: the metric names came from the brief, but DATASUS data does not support
their literal reading. The real definition lives in each metric's `note`, appears in the report JSON,
and is what the LLM receives to comment on.

**Two charts:** daily cases for the last 30 days and monthly cases for the last 12 months, derived
from the same views as the metrics.

**Agent commentary:** one explanation per metric plus an overall summary. Each claim is anchored in
the computed value and/or a retrieved news article, **with the URL cited**. Any source not among the
retrieved articles is discarded in code, not left to the model's judgment.

Full column and metric definitions (in Portuguese):
[`data-and-metrics.md`](.kiro/specs/srag-report-agent/data-and-metrics.md).

---

## API

Every endpoint except `/health` requires the `X-API-Key` header.

| Method | Route | What it does |
|---|---|---|
| `GET` | `/health` | Liveness (no auth) |
| `POST` | `/reports` | **Runs the agent** and returns the full report as JSON |
| `GET` | `/reports/{id}` | Fetches a generated report |
| `GET` | `/reports/{id}/pdf` | Exports the report as PDF |
| `GET` | `/audit/{id}` | **Audit trail** for that report |
| `GET` | `/usage` | Usage and estimated cost, aggregated and per report |
| `GET` | `/metrics` | The 4 metrics with numerator and denominator |
| `GET` | `/data/daily` · `/data/monthly` | Aggregated series for a future front end |
| `GET` | `/charts/daily.png` · `/charts/monthly.png` | Rendered charts |

```bash
KEY=$(grep '^API_KEY=' .env | cut -d= -f2-)
RID=$(curl -s -X POST localhost:8000/reports -H "X-API-Key: $KEY" | jq -r .report_id)
curl -s localhost:8000/audit/$RID -H "X-API-Key: $KEY" | jq
```

> `POST /reports` is **synchronous** and takes ~15 s: it runs the news loop, the embeddings and the
> composition. See [limitations](#known-limitations).

---

## Architecture

API-first and agent-centric, with a strict split between data preparation and runtime.

- **Offline ETL** (`src/etl/`): downloads, cleans, selects columns and anonymizes the DATASUS CSV,
  loading it into Postgres idempotently. Kept apart from the runtime (P6).
- **LangGraph agent** (`src/agent/`): a three-node graph, `metrics` → `news` → `compose`. Metrics are
  deterministic; **the LLM's agency lives only in the news node**, where it writes the query, reads
  the results and decides whether to refine and search again, up to `NEWS_AGENT_MAX_ITERS`
  (ADR-09/ADR-11). Charts are derived outside the graph, straight from the views.
- **Ephemeral RAG** (`src/agent/rag.py`): accumulated news is embedded into an
  `InMemoryVectorStore` rebuilt per request and then discarded. No persistent vector DB, because news
  is ephemeral (ADR-08).
- **Provider-agnostic LLM** (`src/agent/llm.py`): `init_chat_model`; switching Gemini ↔ OpenAI ↔
  Anthropic is a matter of `LLM_PROVIDER`/`LLM_MODEL` (P8).
- **FastAPI API**: the report is a resource. **Streamlit is just a client** of these endpoints, the
  same boundary a future front end would use.

Conceptual diagram: [`docs/architecture/architecture.md`](docs/architecture/architecture.md) ·
full architecture and ADRs (in Portuguese): [`design.md`](.kiro/specs/srag-report-agent/design.md).

---

## Governance and audit

Auditing runs in **two layers** that answer different questions (ADR-13):

| | **Layer 1**: `audit_log` | **Layer 2**: Langfuse |
|---|---|---|
| Answers to | auditor / reviewer | developer |
| Records | decisions and outcome | execution mechanics |
| Lives in | your Postgres | external service |
| Can be turned off? | **no** | yes, and off by default |

**Layer 1 is the compliance record.** Each run stores, event by event, the computed metrics, every
iteration of the tool-calling loop (with the query the model chose and how many results came back),
the decision to stop, the selected news, the composed commentary and the usage. It does not depend
on any external service being up.

```
gather_metrics         {'taxa_mortalidade': 25.39, 'taxa_ocupacao_uti': 33.16, ...}
news_agent.tool_call   query='tendência casos SRAG Brasil'      -> 6 articles
news_agent.tool_call   query='mortalidade SRAG Brasil'          -> 6 articles
news_agent.tool_call   query='ocupação leitos UTI SRAG Brasil'  -> 6 articles
news_agent.tool_call   query='vacinação gripe COVID Brasil'     -> 6 articles
news_agent.stop        model ended the search
news_agent.selected    6 selected for RAG
compose                4 comments, 6 sources
usage                  US$ 0.0337 | 6449 tokens
```

This trail is what lets you reconstruct **why** the agent said what it said. How to access it and
what each event means (in Portuguese): [`docs/auditoria.md`](docs/auditoria.md).

---

## Guardrails

Every trust boundary has an explicit control (P5):

| Boundary | Control |
|---|---|
| Database | Whitelist of parameterized queries in `db/queries.py`; any name outside it is rejected. No free SQL, no text-to-SQL |
| LLM → numbers | The model **never** computes a metric; it receives precomputed values and only interprets them |
| LLM → output | Structured output via a Pydantic schema plus a mandatory disclaimer |
| LLM → sources | Grounding enforced in code: a cited URL not among the retrieved articles is removed |
| Internet | Search with a recency window, source attribution and a loop iteration cap |
| HTTP | API key (`X-API-Key`), rate limiting (`slowapi`) and restricted CORS |
| Secrets | Environment variables only; never in code, logs or the audit trail |

LLM or search failures **degrade instead of breaking**: the news node falls back to a deterministic
search and, at worst, the report ships with valid metrics and charts and flags the missing context.

---

## Sensitive data

- **Minimization at the source:** the ETL keeps only the columns the metrics need and drops direct
  identifiers and quasi-identifiers before loading.
- **Only aggregates leave the database.** Microdata never reaches the API, the LLM, the PDF or the
  audit trail.
- Prompts are built from aggregate values and public news snippets, so by construction there is no
  microdata to leak, including to external tracing.

---

## Cost observability

Each report measures and exposes what it consumed from the three paid resources (P9):

```json
{ "llm_calls": 3, "input_tokens": 4991, "output_tokens": 1720,
  "embedding_calls": 2, "embedding_tokens": 5411, "tavily_searches": 4,
  "estimated_cost_usd": 0.033999, "estimate": true,
  "provider": "google_genai", "model": "gemini-2.5-flash-lite",
  "rates_usd": { "llm_input_per_1m": 0.1, "llm_output_per_1m": 0.4,
                 "embedding_per_1m": 0.15, "tavily_per_search": 0.008 } }
```

The payload stores **the model and the rates applied** next to the value; without them, comparing
reports generated with different models would mislead. It is an **estimate** from configurable rates,
not an invoice, and it is labeled as such. Aggregated at `GET /usage`.

In this example, Tavily searches account for ~94% of the cost and the LLM for ~3%.

---

## Optional tracing (Langfuse)

Layer 2 provides what the trail does not yet: full prompt and response, per-node latency and tokens
per call. **Off by default**; without the variables the application runs identically.

```bash
pip install -r requirements-obs.txt     # in the venv
# .env:  TRACING_ENABLED=true  +  LANGFUSE_PUBLIC_KEY  +  LANGFUSE_SECRET_KEY
```

> **On Docker/Railway** the package is not in the base image: build with
> `--build-arg INSTALL_OBS=true` (`docker-compose.yml` already does). Without the package, tracing
> degrades **silently**. That is the contract, but the trace never shows up.

The `report_id` is used as the trace ID, so the same report can be found in both layers. If Langfuse
is down, missing credentials or disabled, the report is generated normally and `audit_log` stays
complete: **tracing is never on the critical path**.

---

## Tests

```bash
pytest                    # 67 tests
ruff check .              # lint
```

**67 tests.** The 18 integration tests skip automatically without a reachable Postgres; the rest are
pure (no network, no database). Tests that call the real LLM or Tavily skip without a key, and also
skip on `429`/`503` errors, since the Gemini free tier allows 20 requests per day per model.

Two gotchas when running locally:

- **Use the right port.** Against the compose database:
  `DATABASE_URL=postgresql+psycopg2://srag:srag@localhost:5433/srag pytest`. Without it the 18
  integration tests skip silently and look like they "pass".
- **`pytest` clears the `srag_cases` table.** Re-run the seed before demoing the UI.

Test plan and requirement ↔ test traceability: [`tests/TEST_PLAN.md`](tests/TEST_PLAN.md).

---

## Specification (Spec-Driven Development)

Method: **Kiro** structure plus a **constitution** (a GitHub Spec Kit concept) for governance. The
spec documents are written in Portuguese.

| Document | Contents |
|---|---|
| [`constitution.md`](.kiro/steering/constitution.md) | Non-negotiable principles (P1–P9) |
| [`tech.md`](.kiro/steering/tech.md) | Stack and environment-variable contract |
| [`structure.md`](.kiro/steering/structure.md) | Repository layout and conventions |
| [`requirements.md`](.kiro/specs/srag-report-agent/requirements.md) | Requirements in EARS notation |
| [`design.md`](.kiro/specs/srag-report-agent/design.md) | Architecture + 13 ADRs |
| [`data-and-metrics.md`](.kiro/specs/srag-report-agent/data-and-metrics.md) | DATASUS columns + metric definitions |
| [`tasks.md`](.kiro/specs/srag-report-agent/tasks.md) | Implementation plan and open items |

### Where each concern is addressed

| Concern | Where |
|---|---|
| Architecture choices | `design.md` §1–3 + ADR-01 to ADR-13 |
| Governance and transparency | P2 · `governance/audit.py` · `GET /audit/{id}` · [`docs/auditoria.md`](docs/auditoria.md) |
| Guardrails | P5 · SQL whitelist · enforced grounding · schema + disclaimer · API key/rate limit/CORS |
| Tool use | Real tool calling in the news node (ADR-11) + deterministic metric and chart tools |
| Sensitive data | P4 · anonymization in the ETL · only aggregates in the API, the LLM and the trail |
| Clean code | Ruff · type hints · Pydantic at the boundaries · 67 tests |

---

## Known limitations

Recorded honestly; open items are detailed in [`tasks.md`](.kiro/specs/srag-report-agent/tasks.md).

- **`POST /reports` is synchronous** (~15 s). Behind a proxy this flirts with timeouts, and the UI
  gets no progress feedback. The right pattern would be `202 Accepted` plus polling.
- **The trail does not record prompt, response or duration.** You know *what* the agent decided, not
  how long it took or exactly what was sent to the model; today only tracing shows that.
  Tasks T8.1–T8.3.
- **`audit_log` has no retention or immutability.** No purge window and no `REVOKE` of
  `UPDATE`/`DELETE`. Task T8.4.
- **No CI.** `ruff` and `pytest` depend on someone remembering to run them.
- **Unpinned dependencies** (`>=`), which weakens the reproducibility promised in P6.
- **No retry/backoff on LLM calls:** a transient `429` drops straight to the fallback.
- **No numeric check of the commentary.** Grounding validates the cited source, not whether a number
  in the text matches the metric.
- **Deliberately out of scope:** user authentication, a custom front end, DATASUS streaming and high
  availability (ADR-10 and the "out of scope" section of the requirements).
