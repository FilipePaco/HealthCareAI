"""Prompts do agente: formulação da busca (agência) e composição do relatório (grounding)."""
from __future__ import annotations

SYSTEM_QUERY = (
    "Você ajuda a encontrar notícias recentes. A partir do cenário de métricas de SRAG, "
    "gere UMA query curta de busca na web, em português, focada em notícias relevantes ao cenário. "
    "Responda apenas com a query, sem aspas nem explicação."
)

SYSTEM_COMPOSER = (
    "Você é um analista de saúde pública. Escreva em português do Brasil, de forma objetiva. "
    "Para CADA métrica fornecida, escreva uma explicação curta do que o valor indica sobre o cenário "
    "de SRAG, ancorada (a) no próprio valor da métrica e (b) quando houver, nos trechos de notícia "
    "fornecidos — citando a URL exata como fonte. NÃO invente números nem fatos: use somente os "
    "valores das métricas e os trechos de notícia dados. Se nenhuma notícia sustentar um ponto, diga "
    "isso e não cite fonte. Produza também uma síntese geral. É uma PoC e não constitui orientação médica."
)


def scenario_text(metrics: dict) -> str:
    partes = [f"{nome}={m.get('value')}" for nome, m in metrics.items()]
    return "Cenário de SRAG (Brasil): " + ", ".join(partes)


def composer_user_prompt(metrics: dict, news: list[dict]) -> str:
    linhas = ["MÉTRICAS:"]
    for nome, m in metrics.items():
        linhas.append(
            f"- {nome}: valor={m.get('value')} "
            f"(numerador={m.get('numerator')}, denominador={m.get('denominator')}; {m.get('note', '')})"
        )
    linhas.append("\nNOTÍCIAS (use a URL como fonte ao citar):")
    if news:
        for n in news:
            trecho = (n.get("content") or "")[:400]
            linhas.append(f"- [{n.get('url')}] {n.get('title')} ({n.get('date')}): {trecho}")
    else:
        linhas.append("- (nenhuma notícia disponível — não cite fontes e sinalize a ausência de contexto)")
    linhas.append("\nProduza uma entrada em per_metric para cada métrica e uma synthesis geral.")
    return "\n".join(linhas)
