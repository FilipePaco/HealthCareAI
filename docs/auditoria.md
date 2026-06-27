# Como acessar o trilho de auditoria

Toda geração de relatório registra, de forma estruturada e persistente, **cada decisão do agente**
(consulta de métricas, formulação da busca, notícias usadas, composição do comentário). Esse trilho
fica na tabela `audit_log` e é exposto pela API em **`GET /audit/{report_id}`** (protegido por API key).

> O `report_id` aparece no topo do relatório no Streamlit ("Relatório `xxxx`") e também no JSON de
> resposta do `POST /reports`.

---

## Opção 1 — Swagger (navegador, mais fácil)

1. Abra a documentação da API: `https://<URL-DA-API>/docs`
2. Clique em **Authorize** (canto superior direito) e cole a sua **API key** (`X-API-Key`).
3. Expanda **GET `/audit/{report_id}`** → **Try it out**.
4. Cole o `report_id` no campo e clique em **Execute**.
5. A resposta traz o trilho completo, em ordem cronológica.

## Opção 2 — Terminal (curl)

```bash
curl -H "X-API-Key: SUA_API_KEY" \
  https://<URL-DA-API>/audit/SEU_REPORT_ID
```

(para uma saída legível, encadeie com `| python -m json.tool` ou `| jq`)

## Opção 3 — Direto no banco (PostgreSQL)

```sql
SELECT id, ts, event, data
FROM audit_log
WHERE report_id = 'SEU_REPORT_ID'
ORDER BY id;
```

No Railway: service **Postgres** → aba **Data/Query**, ou via `psql` usando o `DATABASE_PUBLIC_URL`.

---

## O que você vê no trilho

Cada linha é um evento com `event`, `ts` (timestamp) e `data` (JSON). A sequência típica:

| Evento | O que registra |
|---|---|
| `gather_metrics` | as 4 métricas calculadas + `data_ref` |
| `formulate_query` | a query de busca que o LLM formulou (agência) |
| `gather_news` | nº de notícias e as URLs recuperadas |
| `gather_news.retry` | (se ocorreu) refino da busca com termos amplos |
| `compose` | o comentário gerado e as fontes citadas |
| `*.error` | (se ocorreu) falha de LLM/busca e o fallback acionado |

Assim é possível **reconstruir e auditar** como cada número e cada afirmação do relatório foram
produzidos — atendendo aos requisitos de **governança e transparência**.

> Observação de privacidade: o trilho guarda apenas **agregados e metadados** — nunca microdados de
> pacientes. Conteúdos binários (ex.: PNG de gráfico) são reduzidos ao seu tamanho, não ao conteúdo.
