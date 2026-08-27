# Deploy no Railway

**Modelo:** 1 projeto → 3 services (mesmo repositório/Dockerfile, start commands diferentes).
Não é preciso um projeto separado para o Streamlit.

```
Projeto "HealthCareAI"
├── Postgres        (banco gerenciado — plugin do Railway)
├── api             (FastAPI)      start: uvicorn ... (CMD padrão do Dockerfile)
└── streamlit       (UI)           start: streamlit run app_streamlit.py ...
```

## Passo a passo

1. **Criar o projeto** e adicionar um **Postgres** (New → Database → PostgreSQL). Ele expõe `DATABASE_URL`.

2. **Service `api`** → New → GitHub Repo (este repo). O Railway detecta o `Dockerfile`.
   - **Variables:**
     - `DATABASE_URL = ${{Postgres.DATABASE_URL}}`  (referência ao serviço Postgres)
     - `GOOGLE_API_KEY = ...`
     - `TAVILY_API_KEY = ...`
     - `API_KEY = <um-segredo-forte>`
     - `LLM_MODEL = gemini-2.5-flash-lite`  (opcional; é o default)
     - `CORS_ORIGINS = *`  (ou a URL pública do Streamlit)
   - **Start command:** já é o do Dockerfile (`uvicorn ... --port ${PORT}`). Nada a fazer.
   - Gere um **domínio público** (Settings → Networking → Generate Domain).

3. **Service `streamlit`** → New → mesmo GitHub Repo (segundo service no mesmo projeto).
   - **Settings → Deploy → Custom Start Command:**
     ```
     streamlit run app_streamlit.py --server.port $PORT --server.address 0.0.0.0
     ```
   - **Variables:**
     - `API_BASE_URL = https://<dominio-publico-do-api>`   (a URL gerada no passo 2)
     - `API_KEY = <o-mesmo-segredo-do-api>`
   - Gere um **domínio público** para acessar a UI.

4. **Popular o banco** (uma vez). Use o Railway CLI apontando para o ambiente do `api`:
   ```bash
   railway link            # selecione o projeto/serviço api
   railway run python -m src.etl.load --year 2024     # dados reais (~194MB)
   # ou: railway run python -m src.etl.seed --rows 5000
   ```

## Langfuse (tracing — camada 2, ADR-13)

Opcional. A aplicação roda igual sem ele (`TRACING_ENABLED=false` é o default) — o trilho de auditoria
em `audit_log` não depende disso.

**Não há infraestrutura a provisionar.** Usamos o **Langfuse Cloud no tier gratuito**; do ponto de
vista de deploy, é mais um serviço externo consumido por API, exatamente como o Tavily.

1. Crie uma conta em [cloud.langfuse.com](https://cloud.langfuse.com) (ou o endpoint da região EU) e
   um projeto. Sem cartão.
2. Em **Settings → API Keys**, gere o par: `pk-lf-…` (public) e `sk-lf-…` (secret).
3. No projeto `HealthCareAI` do Railway, service **`api`**, adicione:
   - `TRACING_ENABLED = true`
   - `LANGFUSE_HOST = https://cloud.langfuse.com`
   - `LANGFUSE_PUBLIC_KEY = pk-lf-...`
   - `LANGFUSE_SECRET_KEY = sk-lf-...`
   Para rodar local, as mesmas quatro linhas no `.env`.
4. Gere um relatório e confirme na UI do Langfuse que o trace aparece com o **`report_id`** como
   identificador — é ele que liga o trace ao `GET /audit/{report_id}`.

**Limites do tier gratuito:** 50k units/mês, 30 dias de retenção, 2 usuários. Um relatório desta PoC
gera ~15–30 observations, então o teto dá na ordem de 2.000 relatórios/mês. Estourar o limite apenas
interrompe a ingestão de traces — **sem cobrança e sem afetar o `audit_log`**. A retenção curta é
irrelevante aqui: o registro com valor probatório é a camada 1, no seu Postgres.

> **E o self-host?** Avaliado e descartado para a PoC: o Langfuse v4 exige seis componentes
> (web, worker, Postgres, ClickHouse, Redis e storage S3), não tem opção single-container, e no
> Railway sairia por ~US$ 30–40/mês contra ~US$ 10 da aplicação inteira. Se um dia houver exigência de
> perímetro ou de retenção longa, a migração é **trocar `LANGFUSE_HOST`** — o código é o mesmo. Ver
> ADR-13.

## Notas
- **Por que 2 services e não 1:** cada service do Railway expõe **uma porta/processo**. API e Streamlit
  são 2 processos → 2 services. Ambos reusam a **mesma imagem** (Dockerfile), mudando só o start command.
- **Streamlit → API:** o Streamlit chama a API **server-side** (httpx), então CORS não se aplica; basta
  `API_BASE_URL` + `API_KEY`. Dá para usar a URL pública do `api` ou a rede privada
  (`http://<api>.railway.internal:${PORT}`).
- **`DATABASE_URL`:** o formato do Railway (`postgresql://...`) funciona direto com SQLAlchemy/psycopg2.
- **Healthcheck:** aponte para `/health` (não exige API key).
- **Custo do LLM:** o free tier do Gemini é limitado; em produção considere billing ou outro provedor
  (troca por `LLM_MODEL`/`LLM_PROVIDER`).
- **Tracing nunca é caminho crítico:** se o Langfuse estiver fora do ar, lento ou sem credenciais, o
  relatório é gerado normalmente e o trilho de auditoria (`audit_log`) segue completo (R11.3).
