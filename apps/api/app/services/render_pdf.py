"""
PDF renderer — printable landscape A4 schedule with embedded Cyrillic fonts
(DejaVu Sans), one page per week block plus the verification report. Layout
mirrors the client-approved xlsx: colored shift cells, legend, quota note.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.spec_draft import min_to_hhmm
from packages.scheduler.spec import OFF, GenerateReport, ScheduleSpec
from packages.scheduler.verifier import build_grid

DAY_NAMES_BG = ["Пон", "Вт", "Ср", "Чет", "Пет", "Съб", "Нед"]

_FONT_DIRS = [
    Path("/usr/share/fonts/truetype/dejavu"),
    Path(__file__).resolve().parent / "fonts",
]
_registered = False


def _register_fonts() -> None:
    global _registered
    if _registered:
        return
    for base in _FONT_DIRS:
        regular, bold = base / "DejaVuSans.ttf", base / "DejaVuSans-Bold.ttf"
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("DejaVu", str(regular)))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
            _registered = True
            return
    raise RuntimeError("DejaVu fonts not found — Cyrillic PDF output requires them")


def render_pdf(spec: ScheduleSpec, report: GenerateReport, month_label: str = "") -> bytes:
    _register_fonts()
    grid = build_grid(report.result.assignments)
    days = spec.days()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm,
        title=f"График — {spec.venue_name}",
    )
    h1 = ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=14, spaceAfter=4, textColor=colors.HexColor("#1A2E44"))
    body = ParagraphStyle("body", fontName="DejaVu", fontSize=8, leading=11)

    story = [
        Paragraph(
            f"МЕСЕЧЕН РАБОТЕН ГРАФИК — {spec.venue_name or 'ShiftFlow'}"
            + (f" — {month_label}" if month_label else ""),
            h1,
        ),
    ]

    for w in range(spec.num_weeks()):
        idx = list(range(w * 7, min((w + 1) * 7, spec.num_days)))
        week_days = [days[i] for i in idx]

        header = ["Служител"] + [f"{DAY_NAMES_BG[d.weekday()]}\n{d.day:02d}.{d.month:02d}" for d in week_days]
        data = [header]
        cell_styles = []
        for r, member in enumerate(spec.staff, start=1):
            row = [member.name]
            for c, d in enumerate(week_days, start=1):
                shift_id = grid.get((member.id, d))
                if shift_id in (None, OFF):
                    row.append("почивка")
                    cell_styles.append(("BACKGROUND", (c, r), (c, r), colors.HexColor("#D9D9D9")))
                else:
                    shift = spec.shift_by_id(shift_id)
                    row.append(f"{min_to_hhmm(shift.start_min)}–{min_to_hhmm(shift.end_min)}")
                    cell_styles.append(("BACKGROUND", (c, r), (c, r), colors.HexColor(shift.color_hex)))
            data.append(row)

        col_widths = [30 * mm] + [(doc.width - 30 * mm) / len(week_days)] * len(week_days)
        table = Table(data, colWidths=col_widths, rowHeights=[9 * mm] + [8 * mm] * len(spec.staff))
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "DejaVu-Bold"),
            ("FONTNAME", (1, 1), (-1, -1), "DejaVu"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C4A63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#E8EEF5")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B0B0B0")),
            *cell_styles,
        ]))
        story.append(KeepTogether([
            Paragraph(f"Седмица {w + 1}", ParagraphStyle(
                "wk", fontName="DejaVu-Bold", fontSize=10, spaceBefore=6, spaceAfter=2)),
            table,
        ]))

    # Legend
    legend_bits = " &nbsp;&nbsp; ".join(
        f'<font backcolor="{s.color_hex}"> {s.duration_h:g}ч {min_to_hhmm(s.start_min)}–{min_to_hhmm(s.end_min)} </font>'
        for s in spec.shifts
    )
    story += [Spacer(1, 4 * mm), Paragraph("ЛЕГЕНДА: " + legend_bits, body)]

    # Verification report
    story += [Spacer(1, 4 * mm), Paragraph("ПРОВЕРКА НА ПРАВИЛАТА", ParagraphStyle(
        "vh", fontName="DejaVu-Bold", fontSize=10, spaceAfter=2))]
    status_label = {"ok": "OK", "relaxed": "невъзможно — минимизирано", "violated": "нарушено"}
    status_bg = {"ok": "#C6EFCE", "relaxed": "#FFEB9C", "violated": "#FFC7CE"}
    vdata = [["Правило", "Статус", "Нарушения", "Детайли"]]
    vstyles = []
    for r, f in enumerate(report.findings, start=1):
        rule = spec.rule_by_id(f.rule_id)
        detail = f.message_bg if f.status != "ok" else (rule.description or "")
        vdata.append([
            Paragraph(f.rule_id, body),
            Paragraph(status_label[f.status], body),
            str(f.violations),
            Paragraph(detail[:220], body),
        ])
        vstyles.append(("BACKGROUND", (1, r), (1, r), colors.HexColor(status_bg[f.status])))
    vtable = Table(vdata, colWidths=[45 * mm, 45 * mm, 20 * mm, doc.width - 110 * mm])
    vtable.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "DejaVu"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A2E44")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B0B0B0")),
        *vstyles,
    ]))
    story.append(vtable)

    doc.build(story)
    return buf.getvalue()
