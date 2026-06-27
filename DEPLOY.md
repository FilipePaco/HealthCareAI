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
