from __future__ import annotations

import shutil

import frontmatter
import pytest

from ictkb.config import get_settings
from ictkb.intake import NAME, run_intake
from ictkb.parsers import UnsupportedFile, extract_text, kind_for


def test_docx_and_xlsx_extraction(tmp_path):
    from docx import Document
    from openpyxl import Workbook

    d = Document()
    d.add_heading("Fee schedule", level=1)
    d.add_paragraph("Tuition is paid per semester.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Level", "Fee"
    t.cell(1, 0).text, t.cell(1, 1).text = "Bachelor", "100000"
    path = tmp_path / "f.docx"
    d.save(path)
    text = extract_text(path)
    assert "# Fee schedule" in text and "| Bachelor | 100000 |" in text

    wb = Workbook()
    ws = wb.active
    ws.title = "Fees"
    ws.append(["Level", "Fee"])
    ws.append(["Masters", 150000])
    wb.save(tmp_path / "f.xlsx")
    assert "| Masters | 150000 |" in extract_text(tmp_path / "f.xlsx")


def test_unsupported_types():
    with pytest.raises(UnsupportedFile):
        kind_for(__import__("pathlib").Path("old.doc"))


def test_filename_pattern():
    assert NAME.match("finance_fee-schedule_2026-09-01.pdf")
    assert NAME.match("programs_course-descriptions~software-engineering_2026-09-01.pdf")
    assert not NAME.match("Finance Fee Schedule.pdf")
    assert not NAME.match("finance_fee-schedule_01-09-2026.pdf")


def test_intake_registers_attachment_and_extracts_text(tmp_path, monkeypatch):
    from docx import Document

    root = tmp_path / "kb"
    shutil.copytree(get_settings().root / "schema", root / "schema")
    shutil.copytree(get_settings().root / "sources", root / "sources")
    (root / "content" / "finance").mkdir(parents=True)
    (root / "incoming" / "finance").mkdir(parents=True)
    monkeypatch.setenv("KB_ROOT", str(root))
    get_settings.cache_clear()
    try:
        d = Document()
        d.add_paragraph("Installments are allowed in three parts.")
        d.save(root / "incoming" / "finance" / "finance_installments_2026-09-01.docx")
        (root / "incoming" / "finance" / "badname.docx").write_bytes(b"x")

        results = run_intake(get_settings(), local_only=True)
        assert {r.file: r.status for r in results} == {
            "finance_installments_2026-09-01.docx": "ok-local", "badname.docx": "rejected"}

        doc = frontmatter.load(root / "content" / "finance" / "finance-installments.md")
        att = doc.metadata["attachments"][0]
        assert att["cloudinary_id"] == "ictu/finance/installments_2026-09-01.docx" and att["kind"] == "docx"
        assert (root / att["text_file"]).read_text(encoding="utf-8").startswith("Installments are allowed")
        assert doc.metadata["status"] == "draft"
        assert (root / "incoming" / "_done" / "finance" / "finance_installments_2026-09-01.docx").exists()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
