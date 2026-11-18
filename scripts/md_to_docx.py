"""Convert the project documents (a Markdown subset) to formatted Word files.

Usage: python scripts/md_to_docx.py docs/report.md docs/report.docx [--font "Times New Roman"] [--size 12]
Supported: headings, paragraphs, bullet and numbered lists, tables, fenced code, **bold** and `code`.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def set_font(run, name, size=None, bold=None, italic=None, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)


PPR_AFTER_SHD = ("w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct", "w:topLinePunct",
                 "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
                 "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc", "w:textDirection",
                 "w:textAlignment", "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr",
                 "w:sectPr", "w:pPrChange")


def shade(properties, fill, paragraph=False):
    """Add background shading; in a paragraph the element must precede spacing, indentation and alignment."""
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    if paragraph:
        properties.insert_element_before(shd, *PPR_AFTER_SHD)
    else:
        properties.append(shd)


def add_inline(paragraph, text, font, size, bold=False):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            set_font(paragraph.add_run(part[2:-2]), font, size, bold=True)
        elif part.startswith("`") and part.endswith("`"):
            set_font(paragraph.add_run(part[1:-1]), "Consolas", size - 1.5, bold=bold)
        else:
            set_font(paragraph.add_run(part), font, size, bold=bold)


def add_page_number(section, font):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    set_font(run, font, 10)
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)


def cell_text(cell, text, font, size, bold=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    add_inline(p, text, font, size, bold=bold)


def add_table(doc, rows, font, size):
    header, body = rows[0], rows[1:]
    width = len(header)
    table = doc.add_table(rows=1, cols=width)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, text in enumerate(header):
        cell = table.rows[0].cells[i]
        cell_text(cell, text, font, size - 1.5, bold=True)
        shade(cell._tc.get_or_add_tcPr(), "E7E6E6")
    trPr = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    trPr.append(repeat)
    for row in body:
        cells = table.add_row().cells
        for i in range(width):
            cell_text(cells[i], row[i] if i < len(row) else "", font, size - 1.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def convert(src: Path, out: Path, font: str, size: float) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.54)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    add_page_number(sec, font)

    normal = doc.styles["Normal"]
    normal.font.name = font
    normal.font.size = Pt(size)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), font)
    for name, pt, italic in (("Heading 1", size + 4, False), ("Heading 2", size + 1.5, False), ("Heading 3", size, True)):
        st = doc.styles[name]
        st.font.name, st.font.size, st.font.bold, st.font.italic = font, Pt(pt), True, italic
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), font)
        st.paragraph_format.space_before = Pt(14)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.keep_with_next = True

    def body_paragraph(text, indent=0.0, align=None, spacing=1.5):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = spacing
        p.paragraph_format.space_after = Pt(6)
        if indent:
            p.paragraph_format.left_indent = Cm(indent)
        if align == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align is None:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_inline(p, text, font, size)
        return p

    i, front, title_done, buffer = 0, True, False, []

    def flush():
        nonlocal buffer
        if buffer:
            body_paragraph(" ".join(buffer))
            buffer = []

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.left_indent = Cm(0.4)
                shade(p._p.get_or_add_pPr(), "F2F2F2", paragraph=True)
                set_font(p.add_run(lines[i].rstrip("\n") or " "), "Consolas", size - 3)
                i += 1
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            i += 1
            continue

        if stripped.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            add_table(doc, rows, font, size)
            continue

        if not stripped:
            flush()
            i += 1
            continue

        mi = re.match(r"^!\[(.*?)\]\((.+?)\)$", stripped)
        if mi:
            flush()
            path = (src.parent / mi.group(2)).resolve()
            if path.exists():
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.keep_with_next = True
                p.add_run().add_picture(str(path), width=Cm(15.5))
                if mi.group(1):
                    cap = body_paragraph(mi.group(1), align="center", spacing=1.0)
                    for run in cap.runs:
                        run.italic = True
                        run.font.size = Pt(size - 1.5)
            i += 1
            continue

        if stripped == "---":
            flush()
            if front and title_done:
                doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
                front = False
            i += 1
            continue

        m = re.match(r"^(#{1,4}) (.*)", stripped)
        if m:
            flush()
            level, text = len(m.group(1)), m.group(2)
            if level == 1 and not title_done:
                for _ in range(5):
                    doc.add_paragraph()
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_font(p.add_run(text), font, size + 8, bold=True)
                doc.add_paragraph()
                title_done = True
            else:
                heading = doc.add_heading(level=max(1, level - 1))
                add_inline(heading, text, font, doc.styles[f"Heading {max(1, level - 1)}"].font.size.pt, bold=True)
                if level == 2 and re.match(r"(Chapter \d|References|Appendix)", text) and not front:
                    heading.paragraph_format.page_break_before = True
            i += 1
            continue

        if front and title_done:  # title page metadata
            body_paragraph(stripped, align="center", spacing=1.15)
            i += 1
            continue

        mb = re.match(r"^[-*] (.*)", stripped)
        mn = re.match(r"^(\d+)\. (.*)", stripped)
        if mb or mn:
            flush()
            marker = "• " if mb else f"{mn.group(1)}. "
            p = body_paragraph(marker + (mb or mn).group(mb and 1 or 2), indent=0.8)
            p.paragraph_format.first_line_indent = Cm(-0.5)
            i += 1
            continue

        buffer.append(stripped)
        i += 1
    flush()
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--font", default="Times New Roman")
    ap.add_argument("--size", type=float, default=12)
    args = ap.parse_args()
    convert(args.source, args.output, args.font, args.size)
    print(f"wrote {args.output}")
