# Decisões Arquiteturais — SRAG Report Agent

Documento que justifica **em detalhe** cada decisão de arquitetura da PoC. Para cada decisão:
**contexto → alternativas consideradas → decisão → justificativa → trade-offs**. As versões curtas
(ADRs) ficam em `.kiro/specs/srag-report-agent/design.md`; aqui está o aprofundamento.

> Princípio guia: é uma **PoC de 5 dias avaliada por arquitetura, governança, guardrails, uso de
> tools, dados sensíveis e clean code**. Cada escolha é otimizada para evidenciar esses critérios,
> não para escala de produção.

---

## 1. Metodologia: SDD com estrutura Kiro + constitution do Spec Kit

**Contexto.** O desafio premia decisões e documentação (3 de 6 critérios). Spec-Driven Development
(SDD) torna o processo de decisão um artefato avaliável.

**Alternativas.**
- *Kiro puro* (`requirements`/`design`/`tasks` em EARS): leve, mas sem lar natural para princípios de
  governança/dados sensíveis.
- *GitHub Spec Kit* (`/specify`→`/plan`→`/tasks` + *constitution*): mais cerimônia e comandos.
- *BMAD* (papéis de agentes): overhead de processo desproporcional ao escopo.

**Decisão.** Esqueleto Kiro + uma `constitution.md` (conceito do Spec Kit) como steering de governança.

**Justificativa.** Os 3 artefatos do Kiro mapeiam 1:1 nos critérios e o `design.md` é o lugar natural
da justificativa arquitetural (critério mais pesado). A constitution preenche exatamente a lacuna que
vale 3 critérios (governança, guardrails, dados sensíveis), transformando "boas intenções" em
princípios versionados e verificáveis. É Markdown puro: funciona dentro da IDE Kiro ou fora dela.

**Trade-offs.** Mais documentos para manter sincronizados. Mitigado por serem curtos e referenciados
entre si.

---

## 2. Linguagem: Python 3.11+

**Contexto.** Stack de GenAI e exigência do desafio.

**Alternativas.** Node/TypeScript (LangChain.js existe), mas ecossistema de dados/LLM menos maduro.

**Decisão.** Python 3.11+.

**Justificativa.** Exigido nos pré-requisitos; ecossistema dominante para LangGraph, pandas,
matplotlib e drivers de Postgres. 3.11+ traz melhor performance e `tomllib`/typing moderno.

**Trade-offs.** Nenhum relevante para o caso.

---

## 3. Orquestração do agente: LangGraph

**Contexto.** O núcleo é um agente que coordena tools (métricas, gráficos, notícias) e um LLM, e o
desafio cobra **registro de decisões dos agentes**.

**Alternativas.**
- *LangChain `AgentExecutor`*: rápido de montar, mas o loop de decisão é mais opaco; auditar exige
  instrumentar callbacks manualmente.
- *CrewAI*: abstração de múltiplos agentes com papéis; bonito no diagrama, porém internals
  "mágicos" — difícil justificar transparência.
- *LlamaIndex Agents*: forte em RAG/indexação, mas nosso caso é mais orquestração de tools que
  recuperação documental.
- *Código próprio* (sem framework): controle total, mas reinventa estado/checkpoint/observabilidade.

**Decisão.** LangGraph.

**Justificativa.** Modela o fluxo como **grafo de estado explícito**: cada etapa (coletar métricas →
gráficos → notícias → compor) é um **nó auditável e checkpointável**. Isso materializa o "registro de
decisões dos agentes" (P2) de forma estrutural, não improvisada. O estado tipado é um contrato claro
(P7), e a natureza determinística do grafo evita o comportamento errático de loops de agente livres.

**Trade-offs.** Mais boilerplate que o `AgentExecutor`. Aceito: o ganho em governança/transparência é
exatamente o que está sendo avaliado.

---

## 4. API web: FastAPI (vs Django, DRF, Flask)

**Contexto.** A solução é **API-first**: o relatório é um recurso consumido por um cliente Streamlit
hoje e por um front-end customizado amanhã; também precisa expor endpoints de exploração de dados e
export de PDF. Não há cadastro de usuários, painel administrativo nem páginas renderizadas no servidor.

**Alternativas consideradas.**

| Critério | **FastAPI** | Django (+DRF) | Flask |
|---|---|---|---|
| Modelo | Async-first, micro-framework de API | Full-stack MVC "batteries included" | Micro-framework síncrono |
| Validação/contratos | **Pydantic nativo** (request/response) | Serializers do DRF (mais boilerplate) | Manual / extensões |
| Concorrência I/O | **async nativo** (ideal p/ LLM+Tavily+DB) | async parcial/retrofitado | síncrono (precisa de gevent etc.) |
| Docs da API | **OpenAPI/Swagger automático** | via libs extras (drf-spectacular) | via extensões |
| Peso / cold start | leve, rápido | pesado (ORM, admin, middleware) | leve |
| Forte quando... | APIs JSON desacopladas, I/O concorrente | apps CRUD com admin, auth, templates | scripts/serviços simples |

**Decisão.** **FastAPI**.

**Justificativa detalhada.**
1. **A força do Django está fora do escopo.** Django brilha em apps full-stack com muitos models,
   painel `admin`, autenticação, sessões e templates server-side. Nossa PoC não tem nada disso: não
   há gestão de usuários nem páginas renderizadas — a apresentação é um cliente desacoplado. Trazer
   Django seria pagar o peso do framework por recursos que não usaríamos.
2. **Concorrência importa aqui.** Gerar um relatório dispara várias chamadas I/O-bound (LLM, busca de
   notícias, queries). O modelo **async-first** do FastAPI permite sobrepor essas esperas e reduzir a
   latência da geração. O suporte async do Django é parcial e retrofitado; o ORM ainda empurra para
   padrões síncronos.
3. **Contratos como cidadãos de primeira classe.** FastAPI usa **Pydantic** nativamente para validar
   e tipar entrada/saída — exatamente o princípio P7 (contratos explícitos nas fronteiras). Com Django
   seria DRF + serializers, mais código para o mesmo efeito.
4. **OpenAPI/Swagger automático.** Atende diretamente o requisito de "deixar os endpoints prontos para
   um front futuro": qualquer dev que for construir o front recebe documentação interativa de graça.
5. **Leveza e deploy.** Menor footprint e cold start mais rápido — melhor para uma PoC no Railway.
6. **Acoplamento de ORM.** Já escolhemos SQLAlchemy (seção 6) por queries analíticas parametrizadas; o
   ORM do Django nos amarraria ao framework. FastAPI + SQLAlchemy é a combinação natural.

*Por que não Flask?* Flask seria leve o suficiente, mas é síncrono por padrão e não traz validação
Pydantic nem OpenAPI sem montar várias extensões — exatamente o que o FastAPI entrega pronto, com peso
semelhante.

**Trade-offs / quando reconsiderar.** Se o projeto evoluísse para um produto com gestão de usuários,
permissões finas, painel administrativo e páginas server-side, Django (com seu admin e auth maduros)
passaria a valer o peso. Para uma **API analítica desacoplada**, FastAPI é o melhor encaixe.

---

## 5. Provedor de LLM: Gemini 2.5 Flash (default) com camada provider-agnostic

**Contexto.** Precisamos de um LLM com bom *function/tool calling* para os comentários ancorados, a
custo viável numa PoC de 5 dias.

**Ponto que mudou a decisão.** A assinatura **Claude Pro NÃO inclui acesso à API**. O plano Pro é para
o uso humano no app (web/desktop/Claude Code); a **API é um produto separado**, cobrada por uso no
`console.anthropic.com` com billing próprio. Ou seja, "usar a API via Pro" não existe — exigiria
habilitar e pagar billing de API à parte.
([fonte](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console))

**Alternativas (comparação para PoC).**

| | Gemini 2.5 Flash | OpenAI gpt-4o-mini | Claude (API) |
|---|---|---|---|
| Free tier | **1.500 req/dia, sem cartão, não expira**; function calling incluído | $5 de crédito, expira em 3 meses | sem free tier; billing à parte |
| Custo da PoC | **R$0** | baixo, mas pago | maior |
| Tool calling | bom | muito bom | excelente |
| Conta do usuário | já possui (Google) | precisa criar/creditar | precisa habilitar API |

**Decisão.** Default **Gemini 2.5 Flash-Lite**, atrás de uma **camada de abstração** (`init_chat_model`
do LangChain) selecionável por variável de ambiente (`LLM_PROVIDER`, `LLM_MODEL`).

> **Nota de cota (aprendizado de implementação):** o `gemini-2.5-flash` tem free tier de apenas
> **20 requisições/dia**, insuficiente para iterar/testar (cada relatório faz 2 chamadas ao LLM, além
> dos testes). O `gemini-2.5-flash-lite` tem cota diária bem maior e bucket separado, por isso virou
> o default. A abstração tornou a troca uma variável de ambiente. Em produção/escala: habilitar
> billing ou trocar para Claude/OpenAI.

**Justificativa detalhada.**
- **Custo zero para construir.** O free tier do Gemini cobre com folga uma PoC de 5 dias e inclui
  *function calling*, que o agente precisa. O usuário já tem conta Google — atrito zero.
- **Sem amarra de fornecedor.** A abstração isola o resto do código do provedor. Se na reta final se
  quiser comentários mais refinados (Claude Sonnet, gpt-4o), troca-se **uma variável de ambiente**,
  sem tocar no agente (P8). Isso permite até um A/B de qualidade de texto sem retrabalho.
- **Robustez do prompt/guardrails.** Os guardrails de saída (grounding, disclaimer, schema) vivem no
  prompt e no parser estruturado — independentes do provedor, então a troca é segura.

**Trade-offs.** Gemini Flash é um modelo mais econômico; a qualidade da redação dos comentários pode
ficar abaixo de modelos maiores. Mitigado pela abstração (upgrade trivial) e pelo fato de o conteúdo
numérico vir determinístico das tools, não do modelo.

---

## 6. Persistência: PostgreSQL no Railway + SQLAlchemy (vs DuckDB, SQLite, NoSQL)

**Contexto.** O agente precisa de uma "tool de consulta ao banco" sobre ~165k linhas, com agregações
analíticas, e deploy simples para PoC.

**Alternativas.**
- *DuckDB*: embarcado, colunar, excelente para agregação analítica sobre CSV/Parquet, zero infra.
- *SQLite*: embarcado e simples, porém fraco em agregações pesadas e concorrência.
- *MongoDB/NoSQL*: dados são tabulares e relacionais por natureza; modelagem documental não agrega.

**Decisão.** **PostgreSQL gerenciado pelo Railway**, acessado via **SQLAlchemy** com queries
parametrizadas (whitelist).

**Justificativa detalhada.**
- **Encaixe com o deploy escolhido.** Postgres é serviço *one-click* no Railway, com `DATABASE_URL`
  injetada por env — exatamente o fluxo de PoC que o usuário quer.
- **Narrativa de arquitetura.** Materializa de forma realista o "banco de dados" do diagrama e o
  caminho para um front futuro que consulta dados agregados via API.
- **Separação ETL ↔ runtime (P6).** A carga do CSV tratado é offline; o runtime só lê tabela curada +
  views — previsível e rápido.
- **Segurança.** SQLAlchemy com parâmetros + whitelist de queries evita SQL injection e SQL arbitrário
  (P5), e centraliza todo acesso em `src/db/queries.py`.

**Trade-offs.** DuckDB seria igualmente capaz e com *menos* infra; foi preterido porque a história de
"banco de dados de verdade" e a evolução para um serviço consumido por múltiplos clientes ficam mais
naturais com Postgres. Para um cenário puramente local/analítico, DuckDB seria a escolha.

---

## 7. Métricas determinísticas (SQL parametrizado) vs text-to-SQL pelo LLM

**Contexto.** Os 4 números são o núcleo de um relatório de **saúde pública**.

**Alternativas.** Deixar o LLM gerar SQL a partir de linguagem natural (text-to-SQL) ou calcular os
números diretamente.

**Decisão.** O LLM **nunca** calcula nem escreve SQL; usa funções/queries **parametrizadas e
versionadas** (P1). O LLM apenas interpreta e comenta os números.

**Justificativa detalhada.** Num relatório de surto, um número alucinado é inaceitável e mina a
credibilidade de toda a solução. SQL parametrizado é **auditável, reproduzível e seguro**. Text-to-SQL
introduziria risco de erro numérico, de query inválida e de execução perigosa — violando P1 e P5. As
definições exatas (denominadores, janelas) estão fixadas em `data-and-metrics.md`, o que torna cada
métrica testável com dados sintéticos de resultado conhecido.

**Trade-offs.** Menos "flexibilidade" para perguntas ad-hoc do usuário em linguagem natural. Aceito: a
PoC entrega um relatório bem definido, não um chat de BI; flexibilidade ad-hoc poderia entrar depois,
com text-to-SQL sob sandbox e validação.

---

## 8. Tool de notícias: Tavily (vs NewsAPI, SerpAPI, scraping)

**Contexto.** O agente embasa comentários em notícias recentes de SRAG, **com fonte citável** (P3).

**Alternativas.** NewsAPI (cobertura boa, atribuição razoável), SerpAPI (resultados de busca, mais
caro), scraping próprio (frágil e com risco legal/manutenção).

**Decisão.** **Tavily** como tool de busca.

**Justificativa.** É uma API de busca **desenhada para agentes**: retorna trechos já com URL e data,
prontos para o grounding e a citação de fonte. Reduz tratamento e dá atribuição confiável. Tem free
tier para PoC e integração pronta com LangChain.

**Trade-offs.** Dependência de terceiro e cota do free tier. Mitigado pelo fallback (R4.4: se a busca
falhar, gera relatório só com métricas e sinaliza ausência de contexto noticioso). A interface de tool
permite trocar o provedor de busca sem afetar o agente.

---

## 9. Gráficos: Matplotlib server-side (vs Plotly)

**Contexto.** Dois gráficos precisam ir tanto para a tela quanto para o **PDF**.

**Decisão.** **Matplotlib** renderizando PNG no servidor.

**Justificativa.** Render determinístico e estático, fácil de **embutir no PDF** e servir via API.
Plotly é superior em interatividade no navegador, mas a interatividade não é requisito e exigiria
render extra (kaleido) para o PDF. Se um front interativo surgir, ele pode pedir os **dados agregados**
via `/data/...` e plotar com a lib que quiser — a API não impõe a biblioteca de gráfico ao cliente.

**Trade-offs.** Gráficos estáticos no Streamlit. Aceito para a PoC.

---

## 10. Interface: Streamlit como **cliente** da API (vs Streamlit acoplado ao banco)

**Contexto.** Precisamos de uma demo visual rápida, mas o usuário quer endpoints prontos para um front
customizado futuro.

**Alternativas.** Streamlit acessando o banco/diretamente as funções (mais rápido de codar, porém
acopla apresentação a dados).

**Decisão.** Streamlit consome **exclusivamente a API** (R8.4) — mesma fronteira de um front futuro.

**Justificativa.** Desacopla apresentação de dados e **valida a própria API** durante a PoC: se o
Streamlit consegue montar o relatório só com os endpoints, um SPA futuro também conseguirá. Evita
duplicar lógica entre "modo Streamlit" e "modo API".

**Trade-offs.** Uma chamada de rede a mais (localhost na PoC) e um pouco mais de código no cliente.
Aceito pelo desacoplamento e pela extensibilidade pedida.

---

## 11. Export de PDF: WeasyPrint (preferido) vs ReportLab

**Contexto.** O relatório precisa ser exportável em PDF (e o diagrama conceitual também é entregue em
PDF).

**Decisão.** **ReportLab** como padrão; WeasyPrint apenas se um layout HTML/CSS rico se tornar
necessário.

**Justificativa.** A exigência de **imagem Docker leve** (seção 16) inverteu a preferência inicial.
WeasyPrint produz layout via HTML/CSS (cômodo), mas exige bibliotecas nativas pesadas
(`cairo`/`pango`/`gdk-pixbuf`) na imagem, o que contraria a meta de leveza. ReportLab é praticamente
*pure-Python* (sem libs de sistema), mantém a imagem enxuta e é mais que suficiente para um relatório
com texto, tabela de métricas e dois PNGs de gráfico. Embutir os PNGs do Matplotlib é direto.

**Trade-offs.** API imperativa mais verbosa que escrever HTML. Aceito em troca de uma imagem menor e
de um build sem dependências nativas. Se o relatório evoluir para um layout muito elaborado,
reavalia-se WeasyPrint (e paga-se o peso das libs nativas).

---

## 12. Governança e auditoria: trilho estruturado por execução

**Contexto.** Critério explícito: mecanismos de auditoria e **registro de decisões dos agentes**.

**Decisão.** Um módulo `governance/audit.py` intercepta toda chamada de tool e LLM e persiste, por
`report_id`, um trilho estruturado (parâmetros, resultados, fontes, prompts/respostas), exposto em
`GET /audit/{id}`.

**Justificativa.** Transforma o agente em algo **inspecionável**: o avaliador (ou um auditor clínico)
consegue refazer o caminho de cada número e cada afirmação. A escolha do LangGraph (seção 3) facilita
isso, pois cada nó é um ponto de captura natural.

**Trade-offs.** Volume de logs. Mitigado por escopo de PoC e por registrar apenas agregados/metadados,
nunca microdados (alinhado à seção 13).

---

## 13. Dados sensíveis: minimização e anonimização na origem

**Contexto.** Dados reais de saúde, mesmo públicos, exigem cuidado (LGPD; critério de avaliação).

**Decisão.** Selecionar apenas colunas necessárias, descartar identificadores na ETL, e **nunca expor
microdados** — API e LLM recebem somente agregados (P4; detalhes em `data-and-metrics.md` §3).

**Justificativa.** Princípios de **minimização e finalidade**: nem o LLM nem o front precisam de
registros individuais para um relatório de métricas, então não há razão para trafegá-los. Reduz a
superfície de risco e é diretamente avaliável.

**Trade-offs.** Perde-se a capacidade de drill-down individual. Desejável neste contexto, não uma perda.

---

## 14. Deploy: Railway (vs Render, Fly.io, VPS)

**Contexto.** PoC que precisa subir rápido, com banco gerenciado.

**Decisão.** **Railway**.

**Justificativa.** Postgres + web service em poucos cliques, variáveis de ambiente simples e bom DX
para PoCs — preferência do usuário e adequada ao prazo. Render e Fly.io seriam equivalentes; um VPS
manual traria overhead de infra desnecessário para 5 dias.

**Trade-offs.** Menos controle de infra que um VPS e custo após o free tier. Irrelevante para a PoC.

---

## 15. Estilo arquitetural: monólito modular (não microsserviços)

**Contexto.** É tentador rotular a solução de "microsserviço", mas o termo precisa ser usado com rigor.

**Esclarecimento conceitual.** "Microsserviços" é um estilo em que a aplicação é composta por
**vários** serviços pequenos, **independentemente deployáveis**, cada um com seu *bounded context* e
(idealmente) seu próprio armazenamento, comunicando-se via rede. Um único serviço, sozinho, **não** é
"um microsserviço".

**O que esta solução é.** Um **monólito modular**: um único serviço de API (FastAPI + runtime do
agente) deployado como uma unidade, internamente separado por módulos com fronteiras claras
(`etl`, `agent`, `agent/tools`, `governance`, `report`, `api`). Ao redor dele há um **cliente**
desacoplado (Streamlit), um **banco** (Postgres) e um **job de ETL** offline — mas isso não os torna
microsserviços.

**Decisão.** Adotar e nomear corretamente como **monólito modular / serviço de API containerizado**.

**Justificativa.**
- **Adequação ao escopo.** Quebrar em serviços independentes (ingestão, agente, relatório) traria
  rede, orquestração e observabilidade distribuída — overhead que **prejudica** clean code e
  simplicidade numa PoC de 5 dias, sem benefício real de escala.
- **Honestidade técnica.** Rotular de "microsserviço" seria *overselling* e um avaliador atento
  notaria. Precisão de vocabulário arquitetural conta a favor.
- **Evolução preservada.** Como os módulos já têm fronteiras explícitas, extrair um deles para um
  serviço próprio no futuro é viável **se e quando** a escala justificar.

**Trade-offs.** Escala-se a aplicação inteira como bloco (não há escala granular por componente).
Irrelevante para a PoC; é o trade-off correto aqui.

---

## 16. Containerização: Docker com imagem leve (multi-stage, python:slim)

**Contexto.** A solução será publicada no Railway e deve ser reproduzível; pediu-se explicitamente uma
**imagem leve**.

**Alternativas de base.**
- *`python:3.11-slim`*: Debian enxuto, **compatível com wheels** pré-compilados (pandas, numpy,
  matplotlib, psycopg2-binary).
- *`python:3.11-alpine`*: menor no papel, mas usa musl libc → **quebra/recompila** wheels científicos,
  estourando tempo de build e, muitas vezes, o tamanho final.
- *`python:3.11` (full)*: traz toolchain e libs que não precisamos em runtime → pesada.

**Decisão.** **Multi-stage** com `python:3.11-slim` nas duas etapas: o *builder* instala dependências
num virtualenv; o *runtime* copia apenas o venv pronto + o código. Roda como usuário **não-root**.
`$PORT` do Railway respeitado.

**Justificativa detalhada.**
- **Slim, não alpine:** para um app de dados/ML, slim é o ponto ótimo — instala wheels binários sem
  recompilar, evitando o efeito colateral clássico do alpine de imagens *maiores* e builds lentos.
- **Multi-stage:** o toolchain de compilação fica no estágio *builder* e **não** entra na imagem
  final; só o venv e o código são copiados → imagem menor e com menor superfície de ataque.
- **Sem dependências nativas:** a escolha de **ReportLab** (seção 11) e do backend `Agg` do Matplotlib
  evita ter que instalar `cairo`/`pango` via `apt`, mantendo a imagem enxuta e o `Dockerfile` sem
  `apt-get`.
- **Só o provedor default:** `requirements.txt` instala apenas `langchain-google-genai`; OpenAI e
  Anthropic ficam comentados, entrando sob demanda — menos peso por padrão.
- **`.dockerignore` agressivo:** exclui `data/` (CSV grande), `.git`, `.kiro/`, `docs/`, testes e
  segredos do contexto de build.
- **Não-root + `$PORT`:** boas práticas de segurança e compatibilidade direta com o Railway.

**Operação.** Uma única imagem serve tanto à API quanto ao Streamlit (diferem só no `command`):
`uvicorn ...` para a API, `streamlit run ...` para o cliente. O `docker-compose.yml` sobe Postgres +
API + Streamlit localmente, dando **paridade** com o Railway (onde o Postgres é serviço gerenciado).

**Trade-offs.**
- A imagem base slim ainda acusa CVEs de sistema operacional em scanners (herdados do Debian);
  mitigável fixando uma tag/digest mais recente e reconstruindo periodicamente — aceitável para PoC.
- Uma imagem compartilhada por API e Streamlit é levemente maior que duas imagens sob medida, mas
  simplifica build e versionamento (um artefato só) — bom trade para o escopo.

---

## 17. RAG efêmero sobre as notícias (vs sem RAG / vector DB persistente)

**Contexto.** Os pré-requisitos do desafio citam "bancos vetoriais, RAG". O grounding dos comentários
usa notícias recuperadas em tempo real (Tavily). Surge a pergunta: vale aplicar RAG aqui?

**Alternativas.**
- *Sem RAG:* injetar todos os trechos retornados direto no prompt. Simples, mas mistura ruído e gasta
  contexto.
- *Vector DB persistente* (Chroma, pgvector, FAISS em disco): indexa notícias ao longo do tempo.
- *RAG efêmero em memória:* embeddar e indexar **por requisição**, recuperar top-k, descartar.

**Decisão.** **RAG efêmero em memória**: a cada relatório, os trechos do Tavily são embeddados
(embeddings do provedor, ex. Gemini `text-embedding`), carregados num **`InMemoryVectorStore`** do
LangChain, e recupera-se o **top-k** mais relevante ao cenário das métricas. O índice é descartado ao
final.

**Justificativa detalhada.**
- **Notícia é efêmera.** O contexto noticioso muda a cada relatório e fica obsoleto rápido. Um índice
  **persistente envelheceria** e exigiria invalidação/atualização — operação sem ganho para o caso.
- **Melhora o sinal.** Mesmo efêmero, o RAG filtra ruído: em vez de despejar tudo no prompt, leva ao
  LLM apenas os trechos mais relevantes ao que as métricas indicam — comentários mais focados e menos
  alucinação por excesso de contexto.
- **Demonstra a técnica sem peso.** Atende o pré-requisito de vetorial/RAG de forma real, mas o
  `InMemoryVectorStore` **não adiciona infra nem dependência pesada** (evita `faiss-cpu`/`chroma`),
  preservando a imagem leve (seção 16).
- **Coerência de stack.** Os embeddings vêm do mesmo provedor abstraído (seção 5); trocar de provedor
  troca também o modelo de embeddings por configuração.

**Trade-offs.** Reprocessa embeddings a cada requisição (custo pequeno: dezenas de trechos). Não há
memória histórica de notícias — desejável aqui, pois cada relatório reflete o momento. Se no futuro se
quisesse análise de tendência noticiosa ao longo do tempo, aí sim um vector DB persistente se
justificaria.

---

## 18. Grau de agência: agência restrita ao nó de notícias

**Contexto.** O enunciado fala em "agente". Há um espectro: desde um pipeline fixo até um agente ReAct
que escolhe livremente quais tools chamar. Onde nos posicionar?

**Alternativas.**
- *Determinístico total:* fluxo fixo, sem decisão do LLM sobre tools. Máxima auditabilidade, baixa
  agência.
- *ReAct livre:* o LLM decide todas as tools e a ordem. Máxima agência, baixa previsibilidade.
- *Agência restrita:* determinismo nos números; agência só onde é seguro.

**Decisão.** **Agência restrita ao nó de notícias.** Métricas e gráficos são determinísticos (queries
parametrizadas, sem decisão do LLM). No nó de notícias, o LLM **formula os termos de busca** a partir
do cenário das métricas e **decide se faz uma rodada extra** de busca refinada, dentro de um limite.

**Justificativa detalhada.**
- **Agência onde agrega, determinismo onde arrisca.** Formular uma boa query de busca é genuinamente
  uma tarefa de linguagem — bom uso do LLM. Já calcular métricas não é: ali, agência só traria risco
  de erro numérico (contra P1).
- **Auditável e seguro.** Mantém os guardrails (P5) e o trilho de auditoria (P2) sob controle: o
  espaço de ações do agente é pequeno e conhecido, fácil de registrar e revisar. Um ReAct livre
  ampliaria a superfície e dificultaria garantir guardrails.
- **"Agente de verdade" para o avaliador.** Evita a crítica de "é só um pipeline", pois há decisão
  real do modelo sobre buscar/refinar, sem cair no extremo imprevisível.

**Trade-offs.** Menos flexível que um agente totalmente autônomo. É o ponto de equilíbrio correto para
um relatório de saúde pública auditável; mais autonomia poderia ser adicionada depois, sob sandbox e
avaliação.

---

## 19. Segurança da API: middleware mínimo (vs autenticação de usuários, vs API aberta)

**Contexto.** A API será publicada no Railway e **dispara chamadas de LLM** (custo). Precisa de
proteção, mas o desafio não pede gestão de usuários. Onde traçar a linha?

**Alternativas.**
- *API aberta:* sem proteção. Simples, mas é um furo de **guardrail** e de **custo** (qualquer um
  dispara LLM à vontade).
- *Autenticação de usuários completa:* cadastro, login, senhas, JWT, roles. Robusto, porém **fora do
  escopo** do desafio.
- *Middleware de segurança mínimo:* API key + rate limiting + CORS.

**Decisão.** **Middleware mínimo**: API key no header `X-API-Key` (segredo via env), **rate limiting**
(`slowapi`) e **CORS** restrito às origens configuradas. **Sem** autenticação de usuários.

**Justificativa detalhada.**
- **Pontua em Guardrails sem creep.** "Guardrails" é critério avaliado; a fronteira HTTP é uma das
  fronteiras de confiança (constitution P5). Proteger a API com pouco código demonstra maturidade de
  deploy e fecha o furo, sem inflar o escopo.
- **Rate limiting é controle de custo.** Além de barrar abuso, limita o *runaway* de chamadas ao LLM —
  preocupação concreta numa PoC com free tier.
- **Autenticação de usuários seria fuga ao escopo.** O desafio é um agente gerador de relatório, sem
  requisito de usuários. Construir login/roles gastaria 1–2 dias em algo **não avaliado** e sinalizaria
  leitura equivocada do brief.
- **Compatível com o cliente desacoplado.** Streamlit (e um front futuro) envia a API key via env; o
  CORS já contempla a origem do front. Não atrapalha a abordagem API-first.

**Trade-offs.** API key é um segredo compartilhado (não identifica usuários individuais nem dá
permissões finas). É exatamente o nível adequado para a PoC; autorização granular entraria só se o
produto evoluísse para multiusuário.
