"""Render do relatório em PDF (ReportLab — pure-Python, mantém a imagem leve; §11)."""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

METRIC_LABELS = {
    "taxa_aumento_casos": "Taxa de aumento de casos",
    "taxa_mortalidade": "Taxa de mortalidade",
    "taxa_ocupacao_uti": "Taxa de ocupação de UTI",
    "taxa_vacinacao": "Taxa de vacinação",
}


def _fmt(value: object) -> str:
    return "N/D" if value is None else f"{value}%"


def build_pdf(report: dict, charts: dict[str, bytes] | None = None) -> bytes:
    """Monta o PDF a partir do dict do relatório e (opcionalmente) dos PNGs dos gráficos."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Relatório de SRAG")
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
    story: list = []

    story.append(Paragraph("Relatório de SRAG", styles["Title"]))
    story.append(Paragraph(f"Data de referência: {report.get('data_ref')}", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    metrics = report.get("metrics", {})
    table_data = [["Métrica", "Valor"]]
    for name, m in metrics.items():
        table_data.append([METRIC_LABELS.get(name, name), _fmt(m.get("value"))])
    table = Table(table_data, hAlign="LEFT", colWidths=[9 * cm, 4 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a6f97")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    commentary = report.get("commentary") or {}
    for c in commentary.get("per_metric", []):
        story.append(Paragraph(METRIC_LABELS.get(c["metric"], c["metric"]), styles["Heading4"]))
        story.append(Paragraph(c.get("explanation", ""), styles["Normal"]))
        if c.get("sources"):
            story.append(Paragraph("Fontes: " + ", ".join(c["sources"]), small))
        story.append(Spacer(1, 0.2 * cm))

    if commentary.get("synthesis"):
        story.append(Paragraph("Síntese", styles["Heading4"]))
        story.append(Paragraph(commentary["synthesis"], styles["Normal"]))
        story.append(Spacer(1, 0.4 * cm))

    for key, title in (("daily", "Casos diários (30 dias)"), ("monthly", "Casos mensais (12 meses)")):
        png = (charts or {}).get(key)
        if png:
            story.append(Paragraph(title, styles["Heading4"]))
            story.append(Image(io.BytesIO(png), width=16 * cm, height=6.4 * cm))
            story.append(Spacer(1, 0.3 * cm))

    if report.get("sources"):
        story.append(Paragraph("Fontes consultadas: " + ", ".join(report["sources"]), small))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(report.get("disclaimer", ""), small))

    doc.build(story)
    return buf.getvalue()
