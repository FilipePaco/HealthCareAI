# Requisitos — SRAG Report Agent

> Notação **EARS** (Easy Approach to Requirements Syntax). Cada requisito é testável e rastreável.
> Padrões EARS usados: *Ubiquitous* (O sistema deve...), *Event-driven* (Quando..., o sistema deve...),
> *State-driven* (Enquanto..., o sistema deve...), *Unwanted* (Se..., então o sistema deve...).

## Visão / Objetivo
Gerar, de forma automatizada e auditável, um **relatório sobre SRAG** que apresente 4 métricas
calculadas a partir dos dados do Open DATASUS, 2 gráficos de série temporal, e comentários do
agente embasados em notícias em tempo real, com rastreabilidade completa das decisões.

## Personas
- **Profissional de saúde / gestor (consumidor do relatório):** quer entender severidade e avanço de surtos.
- **Avaliador técnico / auditor:** quer verificar como cada número e afirmação foram produzidos.

---

## 1. Ingestão e tratamento de dados (ETL)

- **R1.1** *(Ubiquitous)* O sistema deve carregar os dados de internação por SRAG do Open DATASUS
  para um banco PostgreSQL antes de qualquer geração de relatório.
- **R1.2** *(Ubiquitous)* O pipeline de ETL deve selecionar apenas as colunas pertinentes às métricas
  e descartar as demais.
- **R1.3** *(Event-driven)* Quando o pipeline encontrar registros com datas inválidas ou campos
  obrigatórios ausentes, o sistema deve tratá-los segundo regra documentada (descarte ou imputação)
  e registrar a contagem afetada.
- **R1.4** *(Unwanted)* Se uma coluna contiver identificador direto ou quase-identificador não
  utilizado, então o sistema deve removê-la antes da carga (anonimização na origem — P4).
- **R1.5** *(Ubiquitous)* O pipeline deve ser idempotente: reexecutar não duplica dados.

## 2. Métricas (cálculo determinístico)

- **R2.1** *(Ubiquitous)* O sistema deve calcular a **taxa de aumento de casos** comparando janelas
  temporais configuráveis.
- **R2.2** *(Ubiquitous)* O sistema deve calcular a **taxa de mortalidade** entre os casos de SRAG.
- **R2.3** *(Ubiquitous)* O sistema deve calcular a **taxa de ocupação de UTI** entre os casos internados.
- **R2.4** *(Ubiquitous)* O sistema deve calcular a **taxa de vacinação** da população de casos.
- **R2.5** *(Ubiquitous)* Toda métrica deve ser produzida por query SQL parametrizada e versionada,
  nunca calculada pelo LLM (P1).
- **R2.6** *(Event-driven)* Quando uma métrica não puder ser calculada por falta de dados, o sistema
  deve retornar valor nulo explícito com justificativa, em vez de um número inventado.

## 3. Gráficos

- **R3.1** *(Ubiquitous)* O sistema deve gerar um gráfico do **número diário de casos dos últimos 30 dias**.
- **R3.2** *(Ubiquitous)* O sistema deve gerar um gráfico do **número mensal de casos dos últimos 12 meses**.
- **R3.3** *(Ubiquitous)* Os gráficos devem ser gerados a partir dos mesmos dados curados das métricas.

## 4. Notícias em tempo real

- **R4.1** *(Event-driven)* Quando um relatório for solicitado, o agente deve buscar notícias recentes
  sobre SRAG por meio de uma tool de busca.
- **R4.2** *(Ubiquitous)* Cada notícia utilizada deve ter sua **fonte (URL) e data** registradas e
  apresentadas no relatório (P3).
- **R4.3** *(State-driven)* Enquanto a janela de recência configurada não for respeitada, o sistema
  não deve usar a notícia para embasar comentários.
- **R4.4** *(Unwanted)* Se a busca de notícias falhar ou retornar vazio, então o sistema deve gerar o
  relatório com as métricas e sinalizar explicitamente a ausência de contexto noticioso.
- **R4.5** *(Event-driven)* Quando buscar notícias, o agente deve usar uma **ferramenta de busca
  chamável pelo LLM** (*tool-calling*): o modelo **formula a query** a partir do cenário das métricas e
  **decide, em um laço de raciocínio, se refina e repete a busca**, até um limite configurável de
  iterações (agência restrita ao nó de notícias — ADR-09/ADR-11). O agente deve procurar **cobrir as
  quatro dimensões do relatório** (tendência de casos, mortalidade, ocupação de UTI e vacinação) para
  ampliar o lastro noticioso por métrica.
- **R4.6** *(Ubiquitous)* O sistema deve **vetorizar (embeddings)** os trechos de notícia retornados,
  indexá-los em um vector store **em memória** e recuperar o **top-k** mais relevante ao cenário antes
  de embasar os comentários (RAG efêmero, reconstruído por requisição).
- **R4.7** *(Unwanted)* Se o *tool-calling* de notícias falhar (modelo sem suporte a ferramentas, cota
  esgotada ou erro), então o sistema deve **degradar** para uma busca determinística (query formulada
  ou termo padrão), preservando o fallback de R4.4.
- **R4.8** *(Event-driven)* Quando o LLM solicitar uma chamada de ferramenta de busca, o sistema deve
  registrar no trilho de auditoria a query e a contagem de resultados de **cada** iteração (P2).

## 5. Geração do relatório (agente orquestrador)

- **R5.1** *(Event-driven)* Quando um relatório for solicitado, o agente orquestrador deve coordenar
  as tools de métricas, gráficos e notícias e compor um relatório único.
- **R5.2** *(Ubiquitous)* O relatório deve conter as 4 métricas, os 2 gráficos, comentários
  explicativos e a lista de fontes.
- **R5.3** *(Ubiquitous)* Todo comentário do agente deve estar ancorado em uma métrica e/ou notícia
  citada (grounding — P3).
- **R5.4** *(Unwanted)* Se o LLM produzir afirmação sem lastro em métrica ou notícia, então o sistema
  deve descartá-la ou marcá-la como não verificada.
- **R5.5** *(Ubiquitous)* O relatório deve incluir disclaimer de que é uma PoC e não constitui
  orientação médica (P5).
- **R5.6** *(Ubiquitous)* O relatório deve apresentar, para **cada uma das 4 métricas**, uma explicação
  contextual própria (as métricas e as **respectivas** explicações), além de uma síntese geral do cenário.

## 6. Governança, auditoria e transparência

- **R6.1** *(Event-driven)* Quando qualquer tool ou LLM for invocado, o sistema deve registrar
  entrada, saída e timestamp de forma estruturada e persistente (P2).
- **R6.2** *(Ubiquitous)* Cada relatório deve ter um identificador único cujo trilho de auditoria
  pode ser recuperado posteriormente.
- **R6.3** *(Ubiquitous)* O sistema deve expor o trilho de auditoria de um relatório por meio da API.
- **R6.4** *(Event-driven)* Quando o LLM for invocado, o sistema deve registrar no trilho o **prompt
  enviado e a resposta recebida** (truncados, com hash do conteúdo integral), além do modelo e dos
  parâmetros usados — cumprindo o que P2 já promete e hoje não é registrado.
- **R6.5** *(Ubiquitous)* Cada evento do trilho deve ser **tipado** (vocabulário fechado de eventos) e
  carregar `node`, `status` (`ok` / `error` / `fallback`), `duration_ms` e o identificador do evento
  pai, permitindo reconstruir a árvore de execução e o tempo gasto em cada etapa.
- **R6.6** *(Ubiquitous)* O trilho deve registrar a **proveniência** da execução: versão do código
  (git SHA), provedor/modelo de LLM, versão dos prompts e referência do dado de origem (data de carga
  e contagem de linhas da ETL).
- **R6.7** *(Ubiquitous)* O `audit_log` deve ser **append-only** para a aplicação (sem `UPDATE`/`DELETE`)
  e ter **prazo de retenção configurado e documentado** (`AUDIT_RETENTION_DAYS`), conforme LGPD.

## 7. Guardrails e dados sensíveis

- **R7.1** *(Unwanted)* Se uma chamada ao banco não corresponder a uma query da whitelist parametrizada,
  então o sistema deve rejeitá-la (P5).
- **R7.2** *(Ubiquitous)* A API e o LLM devem expor apenas dados agregados, nunca registros individuais (P4).
- **R7.3** *(Ubiquitous)* Segredos (chaves de API, DATABASE_URL) devem vir somente de variáveis de
  ambiente e nunca aparecer em logs.
- **R7.4** *(Unwanted)* Se uma requisição à API chegar sem **API key** válida (header `X-API-Key`),
  então o sistema deve rejeitá-la com `401`.
- **R7.5** *(State-driven)* Enquanto um cliente exceder o limite de requisições configurado, o sistema
  deve responder `429` (rate limiting — também protege contra custo descontrolado de LLM).
- **R7.6** *(Ubiquitous)* A API deve aplicar **CORS** restrito às origens configuradas.
- **R7.7** *(Ubiquitous)* O escopo de segurança é a **proteção mínima da fronteira HTTP**; autenticação
  de usuários (login/cadastro/roles) está **fora de escopo**.

## 8. API e interface

- **R8.1** *(Event-driven)* Quando o cliente chamar `POST /reports`, o sistema deve gerar e retornar
  o relatório em JSON (métricas, referências de gráficos, comentários, fontes, id de auditoria).
- **R8.2** *(Event-driven)* Quando o cliente chamar `GET /reports/{id}/pdf`, o sistema deve retornar
  o relatório renderizado em PDF.
- **R8.3** *(Ubiquitous)* O sistema deve expor endpoints de exploração de dados agregados
  (`GET /metrics`, `GET /data/...`) para consumo por um front-end futuro.
- **R8.4** *(Ubiquitous)* A interface Streamlit deve consumir exclusivamente a API, sem acesso direto
  ao banco (mesma fronteira que um front futuro usaria).

## 9. Deploy

- **R9.1** *(Ubiquitous)* A solução deve ser implantável no Railway com Postgres provisionado e
  configuração via variáveis de ambiente.

## 10. Observabilidade de uso e custo (LLM e busca)

- **R10.1** *(Event-driven)* Quando um relatório for gerado, o sistema deve registrar o uso de **LLM**
  (nº de chamadas e tokens de entrada/saída) e de **busca de notícias** (nº de buscas Tavily) daquele
  relatório.
- **R10.2** *(Ubiquitous)* O sistema deve **estimar o custo aproximado** (USD) a partir de **tarifas
  configuráveis** por token (entrada/saída) e por busca — sem números mágicos (P7); a estimativa é
  rotulada como tal.
- **R10.3** *(Ubiquitous)* O uso/custo deve ser **exposto no JSON do relatório**, **registrado no
  trilho de auditoria** (P2) e disponível de forma **agregada via API** (`GET /usage`).
- **R10.4** *(Ubiquitous)* O registro de uso deve incluir o **modelo efetivamente usado** e a **tarifa
  aplicada**, para que o custo estimado seja interpretável quando o modelo for trocado por env var.
- **R10.5** *(Ubiquitous)* O consumo de **embeddings** do RAG deve ser contabilizado junto do consumo
  de chat — hoje ele fica fora da conta e subestima o custo do relatório.

## 11. Tracing e observabilidade do agente (camada 2)

> Complementa — não substitui — o §6. A camada 1 (`audit_log`) é o registro de conformidade; esta é a
> camada operacional (latência, custo por chamada, replay). Ver ADR-13.

- **R11.1** *(State-driven)* Enquanto `TRACING_ENABLED=true`, o sistema deve emitir para o **Langfuse**
  um **trace por relatório**, com um span por nó do grafo e um span por chamada de LLM, tool e retrieval.
- **R11.2** *(Ubiquitous)* O trace deve ser identificado pelo **`report_id`**, permitindo navegar do
  trilho de auditoria (camada 1) para o trace (camada 2) e vice-versa.
- **R11.3** *(Unwanted)* Se o tracing estiver desabilitado, sem credenciais, ou se o coletor estiver
  indisponível ou lento, então o sistema deve gerar o relatório **normalmente**, sem erro e sem
  degradar a camada 1. O tracing nunca é caminho crítico.
- **R11.4** *(Event-driven)* Quando o LLM solicitar a ferramenta de busca, o sistema deve **executá-la
  como tool do LangChain** (`.invoke` com o `config` de callbacks), de modo que a execução apareça como
  span próprio. *(Hoje `search_news` é chamado diretamente e a execução ficaria invisível no trace.)*
- **R11.5** *(Ubiquitous)* As chamadas de **embeddings** do RAG devem ser instrumentadas — via runnable
  de retrieval ou instrumentação OTel — já que o `CallbackHandler` sozinho não as captura.
- **R11.6** *(Ubiquitous)* O trace de cada chamada de LLM deve conter prompt, resposta, modelo, tokens
  de entrada/saída e latência.
- **R11.7** *(Unwanted)* Se o coletor de tracing for externo à infraestrutura do projeto — que é a
  configuração adotada (Langfuse Cloud, ADR-13) —, então apenas **agregados** podem trafegar: os
  prompts contêm somente valores de métricas e trechos de notícia pública, nunca microdados (P4).
  A garantia é estrutural: os prompts são montados por `scenario_text` / `composer_user_prompt`, que
  só recebem agregados.
- **R11.8** *(Ubiquitous)* O acesso ao Langfuse deve se dar **exclusivamente** por
  `src/governance/tracing.py`; trocar o backend de tracing não deve exigir mudança em outros módulos.

---

## Fora de escopo (PoC)
- Autenticação/autorização de usuários.
- Atualização em streaming dos dados do DATASUS (carga é batch/sob demanda).
- Front-end customizado (apenas os endpoints ficam prontos para ele).
- Alta disponibilidade / escala de produção.
