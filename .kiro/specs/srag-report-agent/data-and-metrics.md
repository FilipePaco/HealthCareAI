# Dados e Definição das Métricas

> Resolve os pontos em aberto de `tasks.md` (Riscos) e `design.md` §2.1. Baseado no **Dicionário de
> Dados SRAG Hospitalizado / SIVEP-Gripe (rev. 23/03/2021)**. Toda definição aqui é a fonte da verdade
> para as queries parametrizadas de `src/db/queries.py` (P1).

## 1. Data de referência (decisão crítica)
Os dados do DATASUS **não são em tempo real** (carga em batch). Portanto "últimos 30 dias" e "últimos
12 meses" são calculados **relativos à data máxima confiável presente no dataset**, não à data de hoje
— senão os gráficos saem vazios.

- `DATA_REF = max(DT_SIN_PRI)` dentre as linhas válidas (ou uma data "as of" passada por parâmetro).
- Campo de tempo primário do caso: **`DT_SIN_PRI`** (data dos primeiros sintomas, obrigatório). É a
  data epidemiológica padrão para curva de casos. `DT_NOTIFIC` fica como fallback se `DT_SIN_PRI`
  for inválida.

## 2. Definição de "caso"
O dataset já é composto por casos de SRAG hospitalizados. Por padrão, **todos os registros válidos**
contam como caso. Recortes (ex.: somente COVID) usam `CLASSI_FIN = 5`. O recorte fica como parâmetro
opcional; o relatório padrão é SRAG geral.

## 3. Colunas selecionadas (P4 — minimização)
Entram no banco apenas: `DT_SIN_PRI`, `DT_NOTIFIC`, `DT_INTERNA`, `DT_ENTUTI`, `DT_SAIDUTI`,
`DT_EVOLUCA`, `HOSPITAL`, `UTI`, `EVOLUCAO`, `CLASSI_FIN`, `VACINA_COV`, `DOSE_1_COV`, `DOSE_2_COV`,
`VACINA`, `NU_IDADE_N`, `CS_SEXO`, `SG_UF`/`SG_UF_NOT`, `CO_MUN_RES`. Demográficos são usados **apenas
em forma agregada**. As ~80 colunas restantes (sintomas detalhados, lotes/laboratório de vacina,
identificadores de unidade, etc.) são descartadas.

## 4. As 4 métricas

### 4.1 Taxa de aumento de casos
Comparação de duas janelas consecutivas de tamanho `REPORT_INCREASE_WINDOW_DAYS` (default **14**),
ancoradas em `DATA_REF`, contando casos por `DT_SIN_PRI`.

```
casos_recentes  = COUNT(*) WHERE DT_SIN_PRI in [DATA_REF-14, DATA_REF]
casos_anteriores= COUNT(*) WHERE DT_SIN_PRI in [DATA_REF-28, DATA_REF-15]
taxa_aumento_%  = (casos_recentes - casos_anteriores) / NULLIF(casos_anteriores,0) * 100
```
- **Decisão:** janela de 14 dias (duas semanas epidemiológicas) é mais estável que diária. Configurável.
- **Borda:** se `casos_anteriores = 0` → retorna nulo com justificativa (R2.6), não divide por zero.

### 4.2 Taxa de mortalidade (CFR — case fatality rate)
```
obitos     = COUNT(*) WHERE EVOLUCAO = 2          -- óbito por SRAG
desfechos  = COUNT(*) WHERE EVOLUCAO IN (1, 2)    -- desfecho conhecido (cura ou óbito)
mortalidade_% = obitos / NULLIF(desfechos,0) * 100
```
- **Decisão de denominador:** sobre **desfechos conhecidos** (`EVOLUCAO IN (1,2)`), não sobre todos os
  casos. Casos em aberto (sem alta/óbito) e `9-Ignorado` distorceriam para baixo. `3-Óbito por outras
  causas` é **excluído** do numerador (não é morte por SRAG).
- **Alternativa documentada:** mortalidade bruta = óbitos / total de casos. Mais simples, mas
  subestima durante surto ativo (muitos casos ainda sem desfecho). Por isso preferimos CFR.

### 4.3 Taxa de ocupação de UTI
**Limitação honesta:** o dataset é de *casos*, não de *leitos*; não há total de leitos de UTI. Logo
"ocupação" no sentido de leitos ocupados/disponíveis **não é calculável**. Adotamos a métrica viável:

```
uti_sim    = COUNT(*) WHERE UTI = 1 AND HOSPITAL = 1
internados = COUNT(*) WHERE HOSPITAL = 1 AND UTI IN (1,2)
taxa_uti_% = uti_sim / NULLIF(internados,0) * 100
```
- **Decisão:** **proporção de internados que necessitaram UTI** (severidade), entre internados com
  info de UTI conhecida. É a leitura defensável com estes dados.
- **Alternativa documentada (futura):** série de "pacientes simultaneamente na UTI" via
  `DT_ENTUTI <= d AND (DT_SAIDUTI >= d OR DT_SAIDUTI IS NULL)` — dá pressão sobre UTI ao longo do
  tempo, mas ainda não é "ocupação" sem o denominador de leitos. Fica registrado como evolução possível.

### 4.4 Taxa de vacinação
```
vacinados  = COUNT(*) WHERE VACINA_COV = 1
conhecidos = COUNT(*) WHERE VACINA_COV IN (1,2)
taxa_vac_% = vacinados / NULLIF(conhecidos,0) * 100
```
- **Limitação honesta:** o enunciado fala "taxa de vacinação da população", mas a única fonte é o
  SRAG, que só informa vacinação **dos casos registrados** — não da população geral. Reportamos como
  **taxa de vacinação COVID entre os casos de SRAG**, com essa ressalva explícita no relatório.
- **Variante opcional:** esquema completo = `DOSE_1_COV IS NOT NULL AND DOSE_2_COV IS NOT NULL`.

## 5. Gráficos
- **Diário (30d):** `COUNT(*) GROUP BY DT_SIN_PRI` para `DT_SIN_PRI in [DATA_REF-29, DATA_REF]`.
- **Mensal (12m):** `COUNT(*) GROUP BY date_trunc('month', DT_SIN_PRI)` para os 12 meses até `DATA_REF`.
- Materializados como **views** (`v_casos_diarios`, `v_casos_mensais`) para acelerar e padronizar.

## 6. Regras de limpeza (ETL)
- Datas: parse `DD/MM/AAAA`; descartar/invalidar datas futuras ou anteriores a 2021; `DT_INTERNA >=
  DT_SIN_PRI` (regra do próprio dicionário).
- Categóricos: normalizar para inteiro; valores fora do domínio → `9-Ignorado`.
- Registrar contagem de linhas afetadas por cada regra (R1.3) para transparência.

## 7. Ressalvas que vão no relatório (transparência)
1. Dados em batch, não tempo real → janelas relativas a `DATA_REF`.
2. Mortalidade = CFR sobre desfechos conhecidos.
3. "Ocupação de UTI" = proporção de internados em UTI (não ocupação de leitos).
4. Vacinação = entre casos de SRAG (não população geral).
