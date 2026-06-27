"""Interface Streamlit — cliente da API (R8.4). Não acessa o banco diretamente."""
from __future__ import annotations

import os

import httpx
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "change-me-local")

METRIC_LABELS = {
    "taxa_aumento_casos": "Aumento de casos",
    "taxa_mortalidade": "Mortalidade",
    "taxa_ocupacao_uti": "Ocupação de UTI",
    "taxa_vacinacao": "Vacinação",
}

st.set_page_config(page_title="SRAG Report Agent", layout="wide")
st.title("Relatório de SRAG — Agente GenAI")

with st.sidebar:
    base = st.text_input("API base URL", API_BASE)
    key = st.text_input("API key", API_KEY, type="password")
    gerar = st.button("Gerar relatório", type="primary")

headers = {"X-API-Key": key}


def _get(path: str) -> httpx.Response:
    return httpx.get(base + path, headers=headers, timeout=120)


if gerar:
    with st.spinner("Rodando o agente (métricas → notícias → comentário)..."):
        try:
            resp = httpx.post(base + "/reports", headers=headers, timeout=240)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao chamar a API: {exc}")
            resp = None
    if resp is not None and resp.status_code == 200:
        st.session_state["report"] = resp.json()
    elif resp is not None:
        st.error(f"Erro {resp.status_code}: {resp.text}")

report = st.session_state.get("report")
if report:
    st.caption(f"Relatório `{report['report_id']}` — data de referência {report.get('data_ref')}")

    cols = st.columns(len(report.get("metrics", {})) or 1)
    for col, (name, m) in zip(cols, report.get("metrics", {}).items(), strict=False):
        valor = "N/D" if m.get("value") is None else f"{m['value']}%"
        col.metric(METRIC_LABELS.get(name, name), valor)

    c1, c2 = st.columns(2)
    daily = _get("/charts/daily.png")
    if daily.status_code == 200:
        c1.image(daily.content, caption="Casos diários (30 dias)")
    monthly = _get("/charts/monthly.png")
    if monthly.status_code == 200:
        c2.image(monthly.content, caption="Casos mensais (12 meses)")

    commentary = report.get("commentary") or {}
    st.header("Comentários do agente")
    for c in commentary.get("per_metric", []):
        st.subheader(METRIC_LABELS.get(c["metric"], c["metric"]))
        st.write(c.get("explanation", ""))
        if c.get("sources"):
            st.caption("Fontes: " + ", ".join(c["sources"]))
    if commentary.get("synthesis"):
        st.subheader("Síntese")
        st.write(commentary["synthesis"])

    usage = report.get("usage")
    if usage:
        with st.expander("Uso e custo estimado deste relatório"):
            u1, u2, u3, u4 = st.columns(4)
            u1.metric("Chamadas LLM", usage.get("llm_calls", 0))
            u2.metric("Tokens (total)", usage.get("total_tokens", 0))
            u3.metric("Buscas Tavily", usage.get("tavily_searches", 0))
            u4.metric("Custo estimado", f"US$ {usage.get('estimated_cost_usd', 0):.4f}")
            st.caption(
                f"Entrada: {usage.get('input_tokens', 0)} tokens · "
                f"Saída: {usage.get('output_tokens', 0)} tokens · "
                "valores são **estimativa** por tarifas configuráveis. Agregado em `GET /usage`."
            )

    st.info(report.get("disclaimer", ""))

    pdf = _get(f"/reports/{report['report_id']}/pdf")
    if pdf.status_code == 200:
        st.download_button(
            "Baixar PDF",
            pdf.content,
            file_name=f"relatorio_{report['report_id']}.pdf",
            mime="application/pdf",
        )
else:
    st.write("Clique em **Gerar relatório** na barra lateral para começar.")
