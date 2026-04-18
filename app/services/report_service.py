from __future__ import annotations

import io
from datetime import date
from typing import Any

from reportlab.lib import colors  # type: ignore[import]
from reportlab.lib.pagesizes import A4  # type: ignore[import]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import]
from reportlab.lib.units import cm  # type: ignore[import]
from reportlab.platypus import (  # type: ignore[import]
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_GREEN = colors.HexColor("#1a7a4a")
_DARK = colors.HexColor("#1a1a2e")
_LIGHT_GREEN = colors.HexColor("#e8f5e9")
_LIGHT_GREY = colors.HexColor("#f5f5f5")


def _delta_str(value: float, lower_is_better: bool = False) -> str:
    if abs(value) < 0.05:
        return "-"
    good = value > 0 if not lower_is_better else value < 0
    arrow = "+" if value > 0 else ""
    marker = "OK" if good else "!!"
    return f"{marker} {arrow}{value:.1f}"


def _parse_analysis(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    headers = {
        "EXECUTIVE SUMMARY",
        "KEY FINDINGS",
        "IMPROVEMENT RECOMMENDATIONS",
        "LONG-TERM OUTLOOK",
    }
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in headers:
            current = stripped
            sections[current] = []
        elif current is not None and stripped:
            sections[current].append(stripped)
    return sections


def generate_pdf_report(
    goal: str,
    zone_name: str,
    zone_type: str,
    actions: list[dict[str, Any]],
    initial_metrics: dict[str, Any],
    final_metrics: dict[str, Any],
    projection_years: int,
    sustainability_score: float,
    overall_outlook: str,
    ai_analysis: str,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "EtTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=_GREEN,
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "EtSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "EtH2",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=_GREEN,
        spaceBefore=14,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "EtBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=3,
    )
    bullet_style = ParagraphStyle(
        "EtBullet",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        leftIndent=14,
        spaceAfter=3,
    )
    goal_style = ParagraphStyle(
        "EtGoal",
        parent=styles["Normal"],
        fontSize=12,
        leading=16,
        textColor=_DARK,
        leftIndent=8,
        spaceAfter=6,
    )

    story: list[Any] = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("Earth Twin", title_style))
    story.append(Paragraph("AI-Powered Urban Sustainability Report", subtitle_style))
    story.append(
        Paragraph(f"Generated: {date.today().strftime('%B %d, %Y')}", subtitle_style)
    )
    story.append(HRFlowable(width="100%", thickness=2, color=_GREEN, spaceAfter=10))

    # ── Goal ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Sustainability Goal", h2_style))
    story.append(Paragraph(f'"{goal}"', goal_style))

    # ── Zone info ───────────────────────────────────────────────────────────
    story.append(Paragraph("Zone Information", h2_style))
    story.append(
        Paragraph(
            f"<b>Zone:</b> {zone_name}    "
            f"<b>Type:</b> {zone_type.title()}    "
            f"<b>Projection period:</b> {projection_years} years",
            body_style,
        )
    )

    # ── Metrics comparison table ─────────────────────────────────────────────
    story.append(Paragraph("Before vs After Metrics", h2_style))

    initial_sus = initial_metrics.get("sustainability_score", 0.0)

    rows: list[list[str]] = [
        ["Metric", "Before", "After", "Change"],
        [
            "Sustainability Score",
            f"{initial_sus:.1f}",
            f"{sustainability_score:.1f}",
            _delta_str(sustainability_score - initial_sus),
        ],
        [
            "Tree Cover",
            f"{initial_metrics.get('tree_cover', 0):.1f}",
            f"{final_metrics.get('tree_cover', 0):.1f}",
            _delta_str(
                final_metrics.get("tree_cover", 0) - initial_metrics.get("tree_cover", 0)
            ),
        ],
        [
            "Biodiversity Score",
            f"{initial_metrics.get('biodiversity_score', 0):.1f}",
            f"{final_metrics.get('biodiversity_score', 0):.1f}",
            _delta_str(
                final_metrics.get("biodiversity_score", 0)
                - initial_metrics.get("biodiversity_score", 0)
            ),
        ],
        [
            "Pollution Level",
            f"{initial_metrics.get('pollution_level', 0):.1f}",
            f"{final_metrics.get('pollution_level', 0):.1f}",
            _delta_str(
                final_metrics.get("pollution_level", 0)
                - initial_metrics.get("pollution_level", 0),
                lower_is_better=True,
            ),
        ],
        [
            "Traffic Level",
            f"{initial_metrics.get('traffic_level', 0):.1f}",
            f"{final_metrics.get('traffic_level', 0):.1f}",
            _delta_str(
                final_metrics.get("traffic_level", 0)
                - initial_metrics.get("traffic_level", 0),
                lower_is_better=True,
            ),
        ],
        [
            "Temperature (C)",
            f"{initial_metrics.get('temperature', 0):.1f}",
            f"{final_metrics.get('temperature', 0):.1f}",
            _delta_str(
                final_metrics.get("temperature", 0)
                - initial_metrics.get("temperature", 0),
                lower_is_better=True,
            ),
        ],
        [
            "Ecosystem Health",
            f"{initial_metrics.get('ecosystem_health', 0):.1f}",
            f"{final_metrics.get('ecosystem_health', 0):.1f}",
            _delta_str(
                final_metrics.get("ecosystem_health", 0)
                - initial_metrics.get("ecosystem_health", 0)
            ),
        ],
        [
            "Risk Level",
            initial_metrics.get("risk_level", "-"),
            final_metrics.get("risk_level", "-"),
            "->",
        ],
    ]

    col_widths = [5.5 * cm, 3 * cm, 3 * cm, 3 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GREEN]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)

    # ── Actions implemented ──────────────────────────────────────────────────
    story.append(Paragraph("Actions Implemented", h2_style))
    for action in actions:
        atype = str(action.get("action_type", "?")).replace("_", " ").title()
        intensity_pct = int(float(action.get("intensity", 0)) * 100)
        duration = action.get("duration_years", 1)
        story.append(
            Paragraph(
                f"<b>{atype}</b>: {intensity_pct}% intensity over {duration} year(s)",
                bullet_style,
            )
        )

    # ── AI Analysis sections ─────────────────────────────────────────────────
    sections = _parse_analysis(ai_analysis)
    section_order = [
        "EXECUTIVE SUMMARY",
        "KEY FINDINGS",
        "IMPROVEMENT RECOMMENDATIONS",
        "LONG-TERM OUTLOOK",
    ]
    for header in section_order:
        lines = sections.get(header, [])
        if not lines:
            continue
        story.append(Paragraph(header.title(), h2_style))
        for line in lines:
            is_list_item = line[:2] in {"* ", "- "} or (
                len(line) > 2 and line[0].isdigit() and line[1] in ".)"
            )
            text = line.lstrip("*-0123456789.) ").strip()
            if text:
                story.append(Paragraph(f"• {text}" if is_list_item else text, bullet_style if is_list_item else body_style))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    footer_style = ParagraphStyle(
        "EtFooter",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        spaceBefore=4,
    )
    story.append(
        Paragraph(
            f"Overall outlook: <b>{overall_outlook.title()}</b>   |   "
            f"Final sustainability score: <b>{sustainability_score:.1f}/100</b>",
            footer_style,
        )
    )
    story.append(
        Paragraph(
            "Generated by Earth Twin — AI-Powered Urban Sustainability Planner",
            footer_style,
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
