"""Report assembly and PDF rendering (ReportLab).

The report only contains results that exist in the session: sections without data
are stated as "not available" rather than filled with placeholders.
"""

from __future__ import annotations

import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

NAVY = colors.HexColor("#10243A")
BLUE = colors.HexColor("#2563EB")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#E2E8F0")
AMBER_BG = colors.HexColor("#FFFBEB")


def report_rows(report: dict) -> pd.DataFrame:
    """Flatten a report dict into section/metric/value rows for CSV export."""
    rows = []
    for section in report["sections"]:
        for label, value in section.get("rows", []):
            rows.append({"section": section["title"], "metric": label, "value": value})
        for note in section.get("notes", []):
            rows.append({"section": section["title"], "metric": "note", "value": note})
    meta = [{"section": "Report", "metric": k, "value": v} for k, v in report["meta"].items()]
    return pd.DataFrame(meta + rows)


def build_pdf(report: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=report["title"], author="EnergyIntel")
    ss = getSampleStyleSheet()
    h_eyebrow = ParagraphStyle("eyebrow", parent=ss["Normal"], fontSize=8, textColor=MUTED, leading=10,
                               fontName="Helvetica-Bold", spaceAfter=2)
    h_title = ParagraphStyle("title", parent=ss["Title"], fontSize=20, textColor=NAVY, alignment=TA_LEFT,
                             leading=24, spaceAfter=4)
    h_sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9.5, textColor=MUTED, leading=13)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, textColor=NAVY, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=9.5, leading=13.5, textColor=colors.HexColor("#1E293B"))
    note = ParagraphStyle("note", parent=body, fontSize=8.5, textColor=MUTED)
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=12)

    story = [
        Paragraph("ENERGYINTEL · ENERGY INTELLIGENCE REPORT", h_eyebrow),
        Paragraph(report["title"], h_title),
        Paragraph(" · ".join(f"{k}: {v}" for k, v in report["meta"].items()), h_sub),
        Spacer(1, 6),
        HRFlowable(width="100%", color=BORDER, thickness=1),
    ]
    if report.get("demo_notice"):
        t = Table([[Paragraph(f"<b>Demonstration data.</b> {report['demo_notice']}", note)]], colWidths=[doc.width])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMBER_BG), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#FDE68A")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [Spacer(1, 8), t]

    for section in report["sections"]:
        story.append(Paragraph(section["title"], h2))
        if section.get("rows"):
            data = [[Paragraph(f"<font color='#64748B'>{a}</font>", cell), Paragraph(f"<b>{b}</b>", cell)]
                    for a, b in section["rows"]]
            t = Table(data, colWidths=[doc.width * 0.45, doc.width * 0.55])
            t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
            story.append(t)
        if section.get("table") is not None and not section["table"].empty:
            tdf = section["table"]
            data = [[Paragraph(f"<b>{c}</b>", cell) for c in tdf.columns]] + \
                   [[Paragraph(str(v), cell) for v in row] for row in tdf.itertuples(index=False)]
            t = Table(data, repeatRows=1, colWidths=[doc.width / len(tdf.columns)] * len(tdf.columns))
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                                   ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            story += [Spacer(1, 4), t]
        for n in section.get("notes", []):
            story += [Spacer(1, 3), Paragraph(n, note if section.get("rows") or section.get("table") is not None else body)]

    story += [Spacer(1, 14), HRFlowable(width="100%", color=BORDER, thickness=1), Spacer(1, 4),
              Paragraph("Forecasts and anomalies are decision-support signals. Validate them with site staff and "
                        "metering records before operational or financial decisions.", note)]

    def _footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, f"EnergyIntel · {report['meta'].get('Generated', '')}")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
