# Diagrama Conceitual — SRAG Report Agent

Fonte do diagrama exigido na entrega (Agente Principal/Orquestrador, Tools, LLM, banco e fontes de
notícias). Exportar para PDF antes de submeter (ver instruções ao final).

```mermaid
flowchart TB
    UI[Streamlit / Front-end futuro]:::ext

    subgraph API["API — FastAPI (API-first)"]
        R1[POST /reports]
        R2[GET /reports/:id/pdf]
        R3[GET /metrics, /data/...]
        R4[GET /audit/:id]
    end

    subgraph AGENT["Agente Orquestrador — LangGraph"]
        ORCH{{Orquestrador<br/>grafo de estado}}
        T1[Tool: Métricas<br/>SQL parametrizado]
        T2[Tool: Gráficos<br/>30d / 12m]
        T3[Tool: Notícias<br/>Tavily · query formulada pelo LLM]
        RAG[RAG efêmero<br/>embeddings + InMemoryVectorStore<br/>retrieve top-k]
        T4[Composer — LLM<br/>explicação por métrica + grounding]
    end

    LLM[/LLM provider-agnostic<br/>Gemini · OpenAI · Anthropic/]:::ext
    DB[(PostgreSQL — Railway<br/>dados curados + views)]
    NEWS[(Notícias web<br/>tempo real)]:::ext
    AUDIT[(Audit log<br/>decisões dos agentes)]

    subgraph ETL["ETL Offline (idempotente)"]
        CSV[CSV Open DATASUS]:::ext --> CLN[Limpeza + seleção<br/>+ anonimização] --> DB
    end

    UI --> API
    API --> ORCH
    ORCH --> T1 --> DB
    ORCH --> T2 --> DB
    ORCH --> T3 --> NEWS
    T3 --> RAG --> LLM
    ORCH --> T4 --> LLM
    API -.audita.-> AUDIT
    ORCH -.audita.-> AUDIT
    API --> AUDIT

    classDef ext fill:#eee,stroke:#999,stroke-dasharray:4 3;
```

## Como exportar para PDF

Opção rápida (sem instalar nada): colar o bloco acima em <https://mermaid.live>, exportar SVG/PNG e
"imprimir para PDF". Ou via CLI:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i docs/architecture/architecture.md -o docs/architecture/architecture.pdf
```
