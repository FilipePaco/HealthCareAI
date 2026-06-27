# Constituição do Projeto — SRAG Report Agent

> Documento de **steering** (princípios invioláveis). Conceito emprestado do GitHub Spec Kit
> e incorporado à estrutura de specs do Kiro. Todo `design.md` e `tasks.md` deve respeitar
> estes princípios. Quando houver conflito entre velocidade e um princípio abaixo, o princípio vence.
>
> Estes princípios endereçam diretamente os critérios de avaliação do desafio:
> **Governança/Transparência**, **Guardrails** e **Tratamento de Dados Sensíveis**.

## P1 — Determinismo nas métricas (não delegar cálculo ao LLM)
As 4 métricas (aumento de casos, mortalidade, ocupação de UTI, vacinação) são calculadas por
**funções/queries SQL parametrizadas e versionadas**, nunca por SQL livre gerado pela LLM nem por
"cálculo mental" do modelo. O LLM **interpreta e comenta** números; ele não os produz.
- **Porquê:** evita alucinação numérica, torna a métrica auditável e reproduzível, e é o que se
  espera de um relatório de saúde pública. Um número errado num relatório de surto é inaceitável.

## P2 — Toda decisão do agente é auditável
Cada execução registra, de forma estruturada e persistente: requisição, cada chamada de tool
(nome, parâmetros, resultado), prompts e respostas do LLM, fontes de notícias usadas, e o
identificador do relatório gerado. Nenhuma etapa é uma "caixa-preta".
- **Porquê:** o desafio cobra explicitamente "mecanismos de auditoria e registro de decisões dos
  agentes". É também requisito de governança para qualquer sistema que apoie decisão clínica.

## P3 — Grounding obrigatório com citação de fonte
Todo comentário/explicação gerado pelo agente deve estar ancorado em (a) uma métrica calculada
deterministicamente e/ou (b) uma notícia recuperada, **com a fonte citada** (URL + data).
Afirmação sem lastro é proibida.
- **Porquê:** transparência e combate a alucinação. O leitor precisa poder verificar a origem de
  cada afirmação.

## P4 — Dados sensíveis: minimização e anonimização na origem
Apenas colunas estritamente necessárias do DATASUS entram no banco. Identificadores diretos e
quase-identificadores não usados são descartados na ETL. **Dados em nível de indivíduo nunca são
expostos pela API nem enviados ao LLM** — apenas agregados.
- **Porquê:** alinhamento com LGPD (minimização, finalidade) e com o critério de "tratamento de
  dados sensíveis". A LLM e o front só precisam de agregados, então não há razão para trafegar
  microdados.

## P5 — Guardrails em toda fronteira de confiança
- **SQL:** somente queries parametrizadas de uma whitelist; nenhuma execução de SQL arbitrário.
- **Notícias:** janela de recência, atribuição de fonte e (quando possível) filtro de domínios.
- **Saída do LLM:** saída estruturada (schema), com disclaimer de que é uma PoC e **não constitui
  orientação médica**.
- **API (fronteira HTTP):** autenticação por **API key**, **rate limiting** (também como controle de
  custo do LLM) e **CORS** restrito. **Sem** autenticação de usuários (fora de escopo) — apenas
  proteção mínima da fronteira.
- **Segredos:** chaves de API somente via variáveis de ambiente; nunca em código ou logs.
- **Porquê:** o critério "Guardrails" é avaliado de forma independente; cada fronteira (banco,
  internet, modelo, **API** e deploy) precisa de um controle explícito.

## P6 — Reprodutibilidade e separação ETL ↔ runtime
A preparação dos dados (download, limpeza, carga) é uma etapa **offline, idempotente e versionada**,
separada do runtime do agente. O agente consome dados já curados.
- **Porquê:** mantém o runtime rápido e previsível, permite recarregar dados sem tocar no agente, e
  deixa o tratamento de dados (crítico, com CSV sujo de 165k linhas) testável isoladamente.

## P7 — Clean code e contratos explícitos
Tipagem (type hints), funções pequenas com responsabilidade única, configuração centralizada,
e contratos de dados (schemas Pydantic) nas fronteiras (API e tools). Sem números mágicos:
limiares e janelas temporais ficam em config.
- **Porquê:** "Clean Code" é critério de avaliação e contratos explícitos reduzem a superfície de bug.

## P8 — Provider-agnostic no LLM
O acesso ao LLM passa por uma única camada de abstração; trocar de provedor (Gemini ↔ OpenAI ↔
Anthropic) é mudança de configuração, não de código.
- **Porquê:** permite desenvolver no free tier do Gemini e migrar para um modelo mais capaz na
  reta final sem retrabalho.
