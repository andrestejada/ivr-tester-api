"""PDF report generation for execution analytics."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Iterable

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.application.dtos.analytics import AnalyticsResponse, RankingItem, Summary, TrendPoint


matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


PAGE_WIDTH, PAGE_HEIGHT = A4


def build_execution_analytics_report_pdf(analytics: AnalyticsResponse) -> bytes:
    """Builds a PDF report for execution analytics."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Reporte de métricas",
        author="IVR Tester",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            spaceBefore=14,
            spaceAfter=6,
        )
    )

    elements: list[object] = []
    elements.append(Paragraph("Reporte de métricas", styles["Title"]))
    elements.append(Paragraph("Resumen de métricas para la arquitectura seleccionada.", styles["BodyText"]))
    elements.append(Spacer(1, 12))

    elements.extend(_build_context_section(analytics, styles))
    elements.extend(_build_summary_section(analytics.summary, styles))
    elements.extend(_build_pie_chart_section(analytics.summary, styles))
    elements.extend(_build_trend_section(analytics.trend, styles))
    elements.extend(_build_rankings_section(analytics.rankings, styles))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _build_context_section(analytics: AnalyticsResponse, styles) -> list[object]:
    context = analytics.selected_context
    rows = [
        ["Arquitectura", context.architecture_name or "Todas"],
        ["Caso de prueba", context.test_case_name or "Todos"],
        [
            "Rango de fechas",
            f"{_format_datetime(context.date_from)} - {_format_datetime(context.date_to)}",
        ],
    ]

    table = Table(rows, colWidths=[140, PAGE_WIDTH - 180])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return [Paragraph("Contexto", styles["SectionHeading"]), table, Spacer(1, 12)]


def _build_summary_section(summary: Summary | None, styles) -> list[object]:
    if summary is None:
        return [
            Paragraph("Resumen", styles["SectionHeading"]),
            Paragraph("No hay datos disponibles para el resumen.", styles["BodyText"]),
            Spacer(1, 12),
        ]

    rows = [
        ["Total de ejecuciones", str(summary.total_executions)],
        ["Exitosas", str(summary.passed_count)],
        ["Fallidas", str(summary.failed_count)],
        ["Errores", str(summary.error_count)],
        ["En ejecución", str(summary.running_count)],
        ["Tasa de éxito", _format_percentage(summary.success_rate)],
        ["Tasa de fallos", _format_percentage(summary.failure_rate)],
        [
            "Duración promedio",
            _format_duration_seconds(summary.avg_duration_seconds),
        ],
    ]

    table = Table(rows, colWidths=[170, PAGE_WIDTH - 210])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return [Paragraph("Resumen", styles["SectionHeading"]), table, Spacer(1, 12)]


def _build_pie_chart_section(summary: Summary | None, styles) -> list[object]:
    if summary is None or summary.total_executions == 0:
        return []

    chart = _render_pie_chart(summary)
    chart_image = Image(chart, width=5.6 * inch, height=3.2 * inch)

    return [
        Paragraph("Distribución de estados", styles["SectionHeading"]),
        chart_image,
        Spacer(1, 12),
    ]


def _build_trend_section(trend: list[TrendPoint] | None, styles) -> list[object]:
    if not trend:
        return []

    chart = _render_trend_chart(trend)
    chart_image = Image(chart, width=6.3 * inch, height=3.4 * inch)

    return [
        Paragraph("Tendencia de ejecuciones", styles["SectionHeading"]),
        chart_image,
        Spacer(1, 12),
    ]


def _build_rankings_section(rankings, styles) -> list[object]:
    if not rankings or (not rankings.top_failed and not rankings.top_success):
        return []

    elements: list[object] = [Paragraph("Rankings", styles["SectionHeading"])]

    if rankings.top_failed:
        elements.append(Paragraph("Casos con más fallos", styles["Heading3"]))
        chart = _render_rankings_chart(rankings.top_failed, "Fallos y éxitos")
        elements.append(Image(chart, width=6.3 * inch, height=3.2 * inch))
        elements.append(Spacer(1, 10))

    if rankings.top_success:
        elements.append(Paragraph("Casos con mejor desempeño", styles["Heading3"]))
        chart = _render_rankings_chart(rankings.top_success, "Éxitos y fallos")
        elements.append(Image(chart, width=6.3 * inch, height=3.2 * inch))
        elements.append(Spacer(1, 10))

    return elements


def _render_pie_chart(summary: Summary) -> io.BytesIO:
    labels = ["Exitosas", "Fallidas", "Errores"]
    values = [summary.passed_count, summary.failed_count, summary.error_count]
    colors_list = ["#10b981", "#ef4444", "#f97316"]

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    ax.pie(
        values,
        labels=labels,
        colors=colors_list,
        autopct=lambda pct: f"{pct:.1f}%" if pct > 0 else "",
        startangle=140,
    )
    ax.axis("equal")
    fig.tight_layout()

    return _figure_to_buffer(fig)


def _render_trend_chart(trend: Iterable[TrendPoint]) -> io.BytesIO:
    dates = [point.date for point in trend]
    total = [point.total for point in trend]
    passed = [point.passed for point in trend]
    failed = [point.failed for point in trend]

    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.plot(dates, total, label="Total", color="#3b82f6", linewidth=2)
    ax.plot(dates, passed, label="Exitosas", color="#10b981", linewidth=2)
    ax.plot(dates, failed, label="Fallidas", color="#ef4444", linewidth=2)

    ax.set_ylabel("Ejecuciones")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.2)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    fig.tight_layout()

    return _figure_to_buffer(fig)


def _render_rankings_chart(items: list[RankingItem], title: str) -> io.BytesIO:
    names = [item.test_case_name for item in items]
    success = [item.success_rate or 0 for item in items]
    failure = [item.failure_rate or 0 for item in items]
    indices = list(range(len(items)))

    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    bar_height = 0.35
    offsets = [index - bar_height / 2 for index in indices]
    offsets_2 = [index + bar_height / 2 for index in indices]

    ax.barh(offsets, failure, height=bar_height, color="#ef4444", label="Fallo")
    ax.barh(offsets_2, success, height=bar_height, color="#10b981", label="Éxito")
    ax.set_yticks(indices)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Porcentaje (%)")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()

    return _figure_to_buffer(fig)


def _figure_to_buffer(fig) -> io.BytesIO:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    buffer.seek(0)
    return buffer


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_percentage(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _format_duration_seconds(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f} s"
