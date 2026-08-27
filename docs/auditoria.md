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
| `news_agent.tool_call` | **cada** iteração do laço: a query que o LLM formulou e nº de resultados |
| `news_agent.stop` | o modelo decidiu encerrar a busca (e por quê) |
| `news_agent.max_iters` | (se ocorreu) o laço bateu no limite de iterações |
| `news_agent.selected` | as notícias que o RAG selecionou para embasar o relatório |
| `news_agent.default_search` | (se ocorreu) o modelo não chamou a tool → busca padrão |
| `compose` | o comentário gerado e as fontes citadas |
| `usage` | tokens de LLM, embeddings, buscas e custo estimado |
| `news_agent.error` · `news_agent.llm_error` | (se ocorreu) falha de tool-calling / do modelo |
| `news_fallback.formulate_query` · `.gather` · `.retry` | (se ocorreu) a busca determinística que substituiu o laço (R4.7) |
| `compose.error` · `gather_news.error` | (se ocorreu) falha na composição ou na busca |

> Os eventos `news_agent.*` são a **agência do agente** registrada passo a passo: dá para ver quais
> termos ele escolheu, quantas vezes refinou e quando decidiu parar.

Assim é possível **reconstruir e auditar** como cada número e cada afirmação do relatório foram
produzidos — atendendo aos requisitos de **governança e transparência**.

> Observação de privacidade: o trilho guarda apenas **agregados e metadados** — nunca microdados de
> pacientes. Conteúdos binários (ex.: PNG de gráfico) são reduzidos ao seu tamanho, não ao conteúdo.

---

## Camada 2 — o trace no Langfuse (opcional)

O `audit_log` acima é o **registro de conformidade**: é ele que responde "de onde veio este número" e
"que notícia embasou esta frase". Ele nunca depende de serviço externo e nunca é desligado.

Quando `TRACING_ENABLED=true`, a mesma execução também é enviada ao **Langfuse**, que responde a
outras perguntas — as de quem está *desenvolvendo*: quanto tempo cada nó levou, qual prompt exato foi
enviado ao modelo, quantos tokens cada chamada consumiu, como duas execuções diferem.

O elo entre os dois é o **`report_id`**, usado também como identificador do trace: com ele em mãos
você acha o mesmo relatório nos dois lugares.

| | `audit_log` (camada 1) | Langfuse (camada 2) |
|---|---|---|
| Para quem | auditor / avaliador | quem desenvolve |
| Registra | decisões e resultado | mecânica da execução |
| Onde vive | seu Postgres | serviço externo |
| Retenção | sua (indefinida hoje; prazo configurável previsto na T8.4) | 30 dias no tier gratuito |
| Pode ser desligado? | não | sim, e é o default |

Se o Langfuse estiver desligado, fora do ar ou sem credenciais, **nada muda**: o relatório é gerado
normalmente e o trilho acima continua completo.
