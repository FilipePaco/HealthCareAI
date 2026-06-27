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
  iterações (agência restrita ao nó de notícias — ADR-09/ADR-11).
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

---

## Fora de escopo (PoC)
- Autenticação/autorização de usuários.
- Atualização em streaming dos dados do DATASUS (carga é batch/sob demanda).
- Front-end customizado (apenas os endpoints ficam prontos para ele).
- Alta disponibilidade / escala de produção.
