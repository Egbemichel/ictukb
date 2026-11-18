"""Text extraction from uploaded files (PDF, Word, spreadsheets, images)."""

from __future__ import annotations

import csv
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
SHEET_EXT = {".xlsx", ".xlsm", ".csv"}
KIND_BY_EXT = {".pdf": "pdf", ".docx": "docx"} | {e: "image" for e in IMAGE_EXT} | {e: "sheet" for e in SHEET_EXT}


class UnsupportedFile(ValueError):
    pass


def kind_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in KIND_BY_EXT:
        raise UnsupportedFile(
            f"{path.name}: unsupported type '{ext}'. Convert .doc to .docx and .xls to .xlsx before uploading."
        )
    return KIND_BY_EXT[ext]


def _md_table(rows: list[list[str]]) -> str:
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [[c.replace("|", "/").replace("\n", " ").strip() for c in r] + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _unwrap(text: str) -> str:
    """Join text that the PDF stored as one word per line."""
    lines = text.splitlines()
    if lines and sum(1 for ln in lines if len(ln.split()) <= 2) / len(lines) > 0.9:
        return " ".join(text.split())
    return text


def extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return _unwrap("\n\n".join(p for p in pages if p))


def extract_docx(path: Path) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(str(path))
    out: list[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, document)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name or "") if para.style is not None else ""
            if style.startswith("Heading ") and style.split()[-1].isdigit():
                out.append("#" * min(int(style.split()[-1]), 6) + " " + text)
            elif style == "Title":
                out.append("# " + text)
            elif style.startswith("List"):
                out.append("- " + text)
            else:
                out.append(text)
        elif tag == "tbl":
            table = Table(child, document)
            out.append(_md_table([[cell.text for cell in row.cells] for row in table.rows]))
    return "\n\n".join(out)


def extract_xlsx(path: Path) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(str(path), read_only=True, data_only=True)
    out = []
    for sheet in workbook.worksheets:
        rows = [["" if c is None else str(c) for c in row] for row in sheet.iter_rows(values_only=True)]
        table = _md_table(rows)
        if table:
            out.append(f"## {sheet.title}\n\n{table}")
    return "\n\n".join(out)


def extract_csv(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return _md_table([list(r) for r in csv.reader(handle)])


def extract_image(path: Path) -> str:
    """OCR through Tesseract when it is installed; otherwise return an empty string."""
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception:
        return ""


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext in {".xlsx", ".xlsm"}:
        return extract_xlsx(path)
    if ext == ".csv":
        return extract_csv(path)
    if ext in IMAGE_EXT:
        return extract_image(path)
    if ext in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    raise UnsupportedFile(f"{path.name}: unsupported type '{ext}'")
