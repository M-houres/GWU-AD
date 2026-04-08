import math
import re
from io import BytesIO
from typing import TYPE_CHECKING, Any

from app.config import get_settings

if TYPE_CHECKING:
    from app.services.processing_engine import ProcessingEngine


settings = get_settings()


def render_detect_report_pdf_reportlab(engine: "ProcessingEngine", result: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    primary = colors.HexColor("#1F4E8C")
    border = colors.HexColor("#D9E1EC")
    panel_bg = colors.HexColor("#F6F8FB")
    body_text = colors.HexColor("#222222")
    muted_text = colors.HexColor("#667085")
    significant = colors.HexColor("#C83A2A")
    significant_bg = colors.HexColor("#FDEDEC")
    suspected = colors.HexColor("#9A6734")
    suspected_bg = colors.HexColor("#FAF1E6")
    gauge_low = colors.HexColor("#2F6DB2")
    gauge_mid = colors.HexColor("#B57A2B")
    gauge_high = colors.HexColor("#C83A2A")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="格物 AIGC 全文检测报告单",
        author="格物",
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DetectTitle",
        parent=base_styles["Title"],
        fontName="STSong-Light",
        fontSize=20,
        leading=24,
        textColor=body_text,
        alignment=1,
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        "DetectSection",
        parent=base_styles["Heading2"],
        fontName="STSong-Light",
        fontSize=12,
        leading=16,
        textColor=primary,
        spaceBefore=4,
        spaceAfter=4,
        wordWrap="CJK",
    )
    meta_label_style = ParagraphStyle(
        "DetectMetaLabel",
        parent=base_styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10.5,
        leading=16,
        textColor=muted_text,
        wordWrap="CJK",
    )
    meta_value_style = ParagraphStyle(
        "DetectMetaValue",
        parent=meta_label_style,
        textColor=body_text,
    )
    table_header_style = ParagraphStyle(
        "DetectTableHeader",
        parent=meta_label_style,
        fontName="STSong-Light",
        fontSize=10,
        leading=14,
        textColor=body_text,
    )
    body_style = ParagraphStyle(
        "DetectBody",
        parent=base_styles["BodyText"],
        fontName="STSong-Light",
        fontSize=11,
        leading=18,
        textColor=body_text,
        wordWrap="CJK",
    )
    full_text_style = ParagraphStyle(
        "DetectFullText",
        parent=body_style,
        fontSize=11.5,
        leading=20,
        firstLineIndent=22,
        spaceAfter=5,
        wordWrap="CJK",
    )
    full_text_significant_style = ParagraphStyle(
        "DetectFullTextHigh",
        parent=full_text_style,
        backColor=significant_bg,
    )
    full_text_suspected_style = ParagraphStyle(
        "DetectFullTextMid",
        parent=full_text_style,
        backColor=suspected_bg,
    )
    full_text_title_style = ParagraphStyle(
        "DetectFullTextTitle",
        parent=body_style,
        fontSize=12,
        leading=18,
        textColor=body_text,
        spaceAfter=4,
        wordWrap="CJK",
    )
    heading_level_1_style = ParagraphStyle(
        "DetectHeading1",
        parent=body_style,
        fontSize=13,
        leading=19,
        textColor=body_text,
        spaceBefore=6,
        spaceAfter=4,
        wordWrap="CJK",
    )
    heading_level_2_style = ParagraphStyle(
        "DetectHeading2",
        parent=body_style,
        fontSize=12,
        leading=18,
        textColor=body_text,
        spaceBefore=5,
        spaceAfter=3,
        wordWrap="CJK",
    )

    meta = engine._current_task_report_meta()
    stats = result.get("source_stats") or {}
    fragment_distribution = result.get("fragment_distribution") or {}
    paragraph_details = result.get("paragraph_details") or []
    suspicious_segments = result.get("suspicious_segments") or []
    band_rows = engine._build_detect_band_rows(paragraph_details)
    detail_map = {int(item.get("index") or 0): item for item in paragraph_details}

    source_text = str(getattr(engine, "_current_detect_source_text", "") or "").strip()
    source_paragraphs = engine._split_detect_paragraphs(source_text)
    if not source_paragraphs:
        source_paragraphs = [str(item.get("excerpt") or "").strip() for item in paragraph_details if item.get("excerpt")]

    def normalize_compare_text(text: str) -> str:
        return re.sub(r"\s+", "", str(text or "")).strip("。；;:：")

    inferred_title = source_paragraphs[0] if source_paragraphs and len(source_paragraphs[0]) <= 80 else ""
    paper_title = meta.get("paper_title") or inferred_title or "未填写"
    authors = meta.get("authors") or "未填写"
    source_filename = meta.get("source_filename") or "未记录"
    domain = re.sub(r"^https?://", "", str(settings.frontend_base_url or "").strip()).rstrip("/") or "www.restin.top"

    score_pct = round(float(result.get("score_pct") or 0.0), 2)
    total_chars = int(stats.get("char_count") or 0)
    ai_chars = min(total_chars, int(round(total_chars * score_pct / 100.0)))
    total_suspected_pct = max(0.0, min(100.0, float(fragment_distribution.get("total_suspected_text_ratio") or 0.0)))
    significant_pct = max(0.0, min(100.0, score_pct))
    suspected_pct = max(0.0, min(100.0 - significant_pct, total_suspected_pct - significant_pct))
    clear_pct = max(0.0, 100.0 - significant_pct - suspected_pct)

    def para(text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(engine._escape_pdf_text(text), style)

    def para_markup(text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(text, style)

    def format_pct(value: float | int | None) -> str:
        return f"{float(value or 0.0):.1f}%"

    def gauge_color(value: float):
        if value >= 30:
            return gauge_high
        if value >= 15:
            return gauge_mid
        return gauge_low

    def risk_label(value: float) -> str:
        if value >= 30:
            return "较高风险"
        if value >= 15:
            return "需要关注"
        return "低风险"

    def band_ai_chars(item: dict[str, Any]) -> int:
        return int(round(int(item.get("char_count") or 0) * float(item.get("avg_score") or 0.0) / 100.0))

    def build_table(rows, col_widths=None, header=False, font_size=9.5):
        table = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
        base_style = [
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("LEADING", (0, 0), (-1, -1), font_size + 4),
            ("TEXTCOLOR", (0, 0), (-1, -1), body_text),
            ("BACKGROUND", (0, 0), (-1, 0), panel_bg if header else colors.white),
            ("GRID", (0, 0), (-1, -1), 0.45, border),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        if header:
            base_style.extend(
                [
                    ("TEXTCOLOR", (0, 0), (-1, 0), body_text),
                    ("FONTNAME", (0, 0), (-1, 0), "STSong-Light"),
                ]
            )
        table.setStyle(TableStyle(base_style))
        return table

    def build_meta_table() -> Table:
        rows = [
            [para("NO", meta_label_style), para(str(result.get("report_no") or "-"), meta_value_style)],
            [para("检测时间", meta_label_style), para(str(result.get("generated_at") or "-"), meta_value_style)],
            [para("篇名", meta_label_style), para(paper_title, meta_value_style)],
            [para("作者", meta_label_style), para(authors, meta_value_style)],
            [para("单位", meta_label_style), para("未填写", meta_value_style)],
            [para("文件名", meta_label_style), para(source_filename, meta_value_style)],
        ]
        table = Table(rows, colWidths=[22 * mm, doc.width - 22 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                    ("LEADING", (0, 0), (-1, -1), 15),
                    ("TEXTCOLOR", (0, 0), (-1, -1), body_text),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return table

    def build_fragment_table() -> Table:
        rows = [
            [
                para("序号", table_header_style),
                para("片段名称", table_header_style),
                para("字符数", table_header_style),
                para("AI特征", table_header_style),
            ]
        ]
        row_styles: list[tuple[int, Any]] = []
        for idx, item in enumerate(suspicious_segments[:6], start=1):
            score_value = float(item.get("score") or 0.0)
            feature_label = "显著" if score_value >= 65 else "疑似"
            rows.append(
                [
                    para(str(idx), meta_value_style),
                    para(f"片段{idx}", meta_value_style),
                    para(str(len(str(item.get("text") or ""))), meta_value_style),
                    para(feature_label, meta_value_style),
                ]
            )
            row_styles.append((idx, significant_bg if feature_label == "显著" else suspected_bg))
        if len(rows) == 1:
            rows.append(
                [
                    para("-", meta_value_style),
                    para("-", meta_value_style),
                    para("0", meta_value_style),
                    para("未识别", meta_value_style),
                ]
            )
        table = build_table(rows, col_widths=[18 * mm, 74 * mm, 34 * mm, 48 * mm], header=True, font_size=10)
        if row_styles:
            table.setStyle(TableStyle([("BACKGROUND", (0, row_index), (-1, row_index), row_color) for row_index, row_color in row_styles]))
        return table

    def segment_spans(paragraph: str, segments: list[dict[str, Any]]) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        for segment in sorted(segments, key=lambda item: len(str(item.get("text") or "")), reverse=True):
            snippet = " ".join(str(segment.get("text") or "").split()).strip()
            if snippet.endswith("..."):
                snippet = snippet[:-3].rstrip()
            if len(snippet) < 6:
                continue
            start = paragraph.find(snippet)
            if start < 0 and len(snippet) > 12:
                snippet = snippet[: max(6, len(snippet) - 8)]
                start = paragraph.find(snippet)
            if start < 0:
                continue
            end = start + len(snippet)
            if any(not (end <= left or start >= right) for left, right, _ in spans):
                continue
            severity = "high" if float(segment.get("score") or 0.0) >= 65 else "mid"
            spans.append((start, end, severity))
        spans.sort(key=lambda item: item[0])
        return spans

    def paragraph_markup(paragraph: str, segments: list[dict[str, Any]]) -> str:
        spans = segment_spans(paragraph, segments)
        if not spans:
            return engine._escape_pdf_text(paragraph)
        parts: list[str] = []
        cursor = 0
        for start, end, severity in spans:
            if start > cursor:
                parts.append(engine._escape_pdf_text(paragraph[cursor:start]))
            color = "#C83A2A" if severity == "high" else "#9A6734"
            back_color = "#FDEDEC" if severity == "high" else "#FAF1E6"
            parts.append(
                f'<font color="{color}" backColor="{back_color}">{engine._escape_pdf_text(paragraph[start:end])}</font>'
            )
            cursor = end
        if cursor < len(paragraph):
            parts.append(engine._escape_pdf_text(paragraph[cursor:]))
        return "".join(parts)

    class OverviewPanel(Flowable):
        def __init__(self, panel_width: float) -> None:
            super().__init__()
            self.width = panel_width
            self.height = 63 * mm

        def wrap(self, availWidth, availHeight):
            return self.width, self.height

        def draw(self):
            canv = self.canv
            canv.saveState()
            canv.setFillColor(panel_bg)
            canv.setStrokeColor(border)
            canv.roundRect(0, 0, self.width, self.height, 6, stroke=1, fill=1)

            canv.setFont("STSong-Light", 10)
            canv.setFillColor(primary)
            canv.drawString(10, self.height - 16, "格物AIGC检测")
            canv.setFont("STSong-Light", 9)
            canv.setFillColor(muted_text)
            canv.drawRightString(self.width - 10, self.height - 16, domain)

            center_x = 34 * mm
            center_y = self.height / 2 + 2 * mm
            radius = 18 * mm

            for tick_index in range(60):
                angle = math.radians(90 - tick_index * 6)
                inner = radius + 2.5 * mm
                outer = inner + (2.8 * mm if tick_index % 5 == 0 else 1.4 * mm)
                x1 = center_x + math.cos(angle) * inner
                y1 = center_y + math.sin(angle) * inner
                x2 = center_x + math.cos(angle) * outer
                y2 = center_y + math.sin(angle) * outer
                canv.setStrokeColor(border)
                canv.setLineWidth(0.5)
                canv.line(x1, y1, x2, y2)

            canv.setStrokeColor(border)
            canv.setLineWidth(8)
            base_path = canv.beginPath()
            base_path.arc(center_x - radius, center_y - radius, center_x + radius, center_y + radius, 0, 360)
            canv.drawPath(base_path, stroke=1, fill=0)

            if significant_pct > 0:
                canv.setStrokeColor(gauge_color(significant_pct))
                canv.setLineWidth(8)
                progress_path = canv.beginPath()
                progress_path.arc(
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                    90,
                    -360 * significant_pct / 100.0,
                )
                canv.drawPath(progress_path, stroke=1, fill=0)

            canv.setFont("STSong-Light", 30)
            canv.setFillColor(body_text)
            canv.drawCentredString(center_x, center_y + 4, format_pct(significant_pct))
            canv.setFont("STSong-Light", 10)
            canv.setFillColor(muted_text)
            canv.drawCentredString(center_x, center_y - 12, "AI特征值")
            canv.setFont("STSong-Light", 9)
            canv.drawCentredString(center_x, 18, f"{ai_chars} / {total_chars}")
            canv.drawCentredString(center_x, 6, "AI特征字符数 / 总字符数")

            metrics = [
                ("AI特征值", format_pct(significant_pct)),
                ("AI特征字符数", str(ai_chars)),
                ("总字符数", str(total_chars)),
                ("风险等级", risk_label(significant_pct)),
            ]
            label_x = 79 * mm
            value_x = self.width - 12
            metric_y = self.height - 34
            for label, value in metrics:
                canv.setFont("STSong-Light", 10.5)
                canv.setFillColor(muted_text)
                canv.drawString(label_x, metric_y, label)
                canv.setFont("STSong-Light", 11.5)
                canv.setFillColor(body_text)
                canv.drawRightString(value_x, metric_y, value)
                metric_y -= 16

            legends = [
                ("AI特征显著（计入AI特征字符数）", significant),
                ("AI特征疑似（未计入AI特征字符数）", suspected),
                ("未标识部分", muted_text),
            ]
            legend_y = 28
            for legend_text, legend_color in legends:
                canv.setFillColor(legend_color)
                canv.rect(label_x, legend_y - 2, 9, 5, stroke=0, fill=1)
                canv.setFillColor(muted_text)
                canv.setFont("STSong-Light", 8.5)
                canv.drawString(label_x + 14, legend_y - 1, legend_text)
                legend_y -= 14

            canv.restoreState()

    class DistributionPanel(Flowable):
        def __init__(self, panel_width: float) -> None:
            super().__init__()
            self.width = panel_width
            self.height = 43 * mm

        def wrap(self, availWidth, availHeight):
            return self.width, self.height

        def draw(self):
            canv = self.canv
            canv.saveState()
            canv.setFillColor(panel_bg)
            canv.setStrokeColor(border)
            canv.roundRect(0, 0, self.width, self.height, 6, stroke=1, fill=1)

            content_x = 10
            column_width = (self.width - 20) / 3.0
            top_y = self.height - 18
            for index, item in enumerate(band_rows):
                band_x = content_x + index * column_width
                canv.setFont("STSong-Light", 10)
                canv.setFillColor(body_text)
                canv.drawString(band_x, top_y, str(item.get("label") or "-"))
                canv.setFont("STSong-Light", 9)
                canv.setFillColor(muted_text)
                canv.drawString(band_x, top_y - 15, f"AI特征值：{format_pct(item.get('avg_score') or 0.0)}")
                canv.drawString(band_x, top_y - 29, f"AI特征字符数：{band_ai_chars(item)}")

            bar_x = 10
            bar_y = 10
            bar_width = self.width - 20
            bar_height = 10
            current_x = bar_x
            ratio_rows = [
                (significant_pct, significant),
                (suspected_pct, suspected),
                (clear_pct, border),
            ]
            for ratio, fill_color in ratio_rows:
                segment_width = bar_width * max(0.0, ratio) / 100.0
                if segment_width <= 0:
                    continue
                canv.setFillColor(fill_color)
                canv.rect(current_x, bar_y, segment_width, bar_height, stroke=0, fill=1)
                current_x += segment_width

            canv.setStrokeColor(border)
            canv.rect(bar_x, bar_y, bar_width, bar_height, stroke=1, fill=0)
            canv.setFont("STSong-Light", 8.5)
            canv.setFillColor(muted_text)
            canv.drawString(bar_x, 1.5, "0")
            canv.drawRightString(bar_x + bar_width, 1.5, str(total_chars))
            canv.restoreState()

    story: list[Any] = [para("AIGC检测 · 全文报告单", title_style), build_meta_table(), Spacer(1, 3)]

    story.append(KeepTogether([para("全文检测结果", section_style), OverviewPanel(doc.width), Spacer(1, 5)]))
    story.append(KeepTogether([para("AIGC片段分布图", section_style), DistributionPanel(doc.width), Spacer(1, 5)]))
    story.append(para("片段指标列表", section_style))
    story.append(build_fragment_table())
    story.append(Spacer(1, 6))
    story.append(para("原文内容", section_style))

    if paper_title and (not source_paragraphs or normalize_compare_text(paper_title) != normalize_compare_text(source_paragraphs[0])):
        story.append(para(paper_title, full_text_title_style))

    if source_paragraphs:
        for paragraph_index, paragraph in enumerate(source_paragraphs, start=1):
            detail = detail_map.get(paragraph_index, {})
            heading_level, _heading = engine._detect_outline_heading(paragraph)
            if heading_level is not None and len(paragraph) <= 48:
                heading_style = heading_level_1_style if heading_level <= 1 else heading_level_2_style
                story.append(para(paragraph, heading_style))
                continue

            paragraph_segments = detail.get("suspicious_segments") or []
            paragraph_style = full_text_style
            if str(detail.get("label") or "").lower() == "high":
                paragraph_style = full_text_significant_style
            elif paragraph_segments or str(detail.get("label") or "").lower() == "medium":
                paragraph_style = full_text_suspected_style
            story.append(para_markup(paragraph_markup(paragraph, paragraph_segments), paragraph_style))
    else:
        story.append(para("未获取到正文内容。", body_style))

    story.append(Spacer(1, 8))
    story.append(para("说明:", section_style))
    story.extend(
        [
            para("1. 支持中、英文内容检测；", body_style),
            para("2. AI特征值 = AI特征字符数 / 总字符数；", body_style),
            para("3. 红色代表AI特征显著部分，计入AI特征字符数；", body_style),
            para("4. 棕色代表AI特征疑似部分，未计入AI特征字符数；", body_style),
            para("5. 检测结果仅供参考，最终判定仍需结合人工复核、机构审查及具体学术政策综合判断。", body_style),
        ]
    )

    def draw_page(canvas, _doc):
        width, height = A4
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.setLineWidth(0.5)
        canvas.line(_doc.leftMargin, height - 11 * mm, width - _doc.rightMargin, height - 11 * mm)
        canvas.line(_doc.leftMargin, 11 * mm, width - _doc.rightMargin, 11 * mm)
        canvas.setFont("STSong-Light", 9)
        canvas.setFillColor(muted_text)
        canvas.drawString(_doc.leftMargin, height - 8.2 * mm, "格物AIGC检测服务")
        canvas.drawRightString(width - _doc.rightMargin, height - 8.2 * mm, domain)
        canvas.drawCentredString(width / 2.0, 7.8 * mm, f"— {_doc.page} —")
        canvas.drawRightString(width - _doc.rightMargin, 7.8 * mm, domain)
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue()
