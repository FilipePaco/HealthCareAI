# Plano de Testes

> Documentação **precede** a implementação de cada teste (convenção do projeto). Cada caso referencia
> o requisito (Rx.y) e/ou a regra de `data-and-metrics.md` que valida. Atualize esta tabela ao
> adicionar novos testes.

## Estratégia
- **Funções puras primeiro:** a limpeza (ETL) e os cálculos são testados com **dados sintéticos** de
  resultado conhecido — sem rede, sem banco. Garante P1 (métricas determinísticas) e R1.x (ETL).
- **Fronteiras com schema:** contratos Pydantic validados nos testes de API (fase posterior).
- **Guardrails:** cada guardrail tem um teste de rejeição (ex.: query fora da whitelist, request sem
  API key, comentário sem fonte).

## Cobertura por módulo

### `src/etl/clean.py` — limpeza e seleção (Fase 1)
| Teste | O que valida | Ref |
|---|---|---|
| `test_select_columns_drops_identifiers_and_extras` | Mantém só colunas selecionadas; descarta identificadores/colunas não usadas | R1.2, R1.4 / §3 |
| `test_drops_rows_without_dt_sin_pri` | Linhas sem data primária (ausente ou ilegível) são removidas e contadas | R1.3 / §1 |
| `test_categorical_out_of_domain_becomes_9` | Categórico fora do domínio vira 9-Ignorado; contagem reportada | R1.3 / §6 |
| `test_classi_fin_out_of_domain_becomes_na` | CLASSI_FIN (sem código 9) fora do domínio vira NA | §6 |
| `test_dates_out_of_bounds_invalidated` | Datas futuras ou anteriores a 2021 viram NaT (e derrubam a linha se for DT_SIN_PRI) | R1.3 / §6 |
| `test_interna_before_sintomas_invalidated` | DT_INTERNA < DT_SIN_PRI é invalidada e contada | §6 |
| `test_cleaning_report_counts` | O CleaningReport reporta rows_in/rows_out e contagens coerentes | R1.3 |
| `test_idempotent_on_clean_input` | Reaplicar clean em dados já limpos não altera o resultado | R1.5 |

### `src/db/queries.py` + `src/etl/load.py` — métricas e carga (Fase 1/2) — *integração c/ Postgres*
| Teste | O que valida | Ref |
|---|---|---|
| `test_taxa_mortalidade_conhecida` | CFR = óbitos / desfechos conhecidos, valor exato | R2.2 / §4.2 |
| `test_taxa_ocupacao_uti_conhecida` | UTI=1 sobre internados (hospital=1, uti∈{1,2}), valor exato | R2.3 / §4.3 |
| `test_taxa_vacinacao_conhecida` | vacina_cov=1 sobre conhecidos, valor exato | R2.4 / §4.4 |
| `test_taxa_aumento_casos_janelas` | Janelas half-open de N dias; (rec−ant)/ant×100 | R2.1 / §4.1 |
| `test_metrica_sem_dados_retorna_none` | Denominador 0 → valor None (sem divisão por zero) | R2.6 |
| `test_series_diaria_e_mensal` | Séries dos últimos 30d/12m a partir das views | R3.1–R3.3 |
| `test_whitelist_rejeita_metrica_desconhecida` | `run_metric` com nome fora da whitelist → ValueError | R7.1 |
| `test_carga_idempotente` | Recarregar o mesmo dado não duplica linhas | R1.5 |

> Os testes de integração usam Postgres (docker compose `db`). Se o banco estiver indisponível,
> são automaticamente **pulados** (skip) — a suíte unitária pura segue rodando.

### `src/agent/tools/chart_tool.py` — gráficos (Fase 2) — *puro, sem rede/banco*
| Teste | O que valida | Ref |
|---|---|---|
| `test_densify_daily_fills_missing_with_zero` | Últimos N dias contínuos; dias sem caso viram 0 | R3.1 |
| `test_densify_monthly_fills_12_months` | Últimos N meses contínuos; meses sem caso viram 0 | R3.2 |
| `test_render_bar_returns_png` | `render_bar` devolve PNG válido (assinatura `\x89PNG`) | R3.3 |
| `test_daily_and_monthly_charts_png` | `daily_chart`/`monthly_chart` devolvem PNG a partir de série sintética | R3.1–R3.3 |
| `test_charts_handle_empty_series` | Série vazia ainda gera PNG (não quebra) | R3.3 |

## Pendentes (fases seguintes — documentar antes de implementar)
- `src/agent/rag.py`: retrieve top-k retorna os trechos mais relevantes (R4.6).
- `src/agent/...`: comentário sem fonte é descartado/marcado (R5.4).
- `src/api/security.py`: request sem API key -> 401; excesso -> 429 (R7.4, R7.5).
