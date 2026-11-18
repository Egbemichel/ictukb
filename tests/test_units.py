from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import frontmatter

from ictkb.chunking import chunk_markdown
from ictkb.config import get_settings
from ictkb.connectors import sheets, web
from ictkb.content import ContentDoc, validate
from ictkb.embedding import HashEmbedder
from ictkb.evaluation import matches
from ictkb.search import build_tsquery
from ictkb.util import detect_language, is_stale, slugify


def make_doc(tmp_path: Path, **over) -> ContentDoc:
    settings = get_settings()
    meta = {
        "id": "finance-test", "title": "Test document", "category": "finance", "source_type": "official_doc",
        "freshness_tier": "semester", "status": "draft", "last_verified": date.today().isoformat(),
        "owner": "handle", "program_level": ["all"], "tags": [], "related": [],
    }
    body = over.pop("_body", "Some body text that is long enough to count.")
    meta.update(over)
    path = settings.content_dir / "finance" / f"{meta['id']}.md"
    return ContentDoc(meta=meta, body=body, path=path)


def test_slugify_and_language():
    assert slugify("Software Engineering / Year 2") == "software-engineering-year-2"
    assert slugify("Génie logiciel") == "genie-logiciel"
    assert detect_language("Les étudiants doivent payer les frais pour la rentrée et le dossier") == "fr"
    assert detect_language("Students must pay the fees for the semester and the form") == "en"


def test_staleness_limits():
    old = (date.today() - timedelta(days=130)).isoformat()
    assert is_stale("semester", old)
    assert not is_stale("static", old)
    assert is_stale("realtime", (date.today() - timedelta(days=2)).isoformat())
    assert not is_stale("realtime", (date.today() - timedelta(days=2)).isoformat(), max_age_days=7)


def test_chunking_keeps_headings_and_splits_tables():
    rows = "\n".join(f"| Course {i} | {i} |" for i in range(200))
    body = f"## Fees\n\nIntro paragraph.\n\n### Table\n\n| Name | Credits |\n|---|---|\n{rows}"
    chunks = chunk_markdown("Fee schedule", body, max_tokens=120)
    assert len(chunks) > 3
    assert all(c.content.startswith("Fee schedule") for c in chunks)
    table_chunks = [c for c in chunks if "| Name | Credits |" in c.content]
    assert len(table_chunks) >= 3  # header repeated on every piece
    assert chunks[0].heading_path == "Fees"
    assert any(c.heading_path == "Fees > Table" for c in chunks)


def test_tsquery_drops_stopwords():
    assert build_tsquery("How do I pay fees in installments?") == "pay | fees | installments"
    assert build_tsquery("is it") == "zzzznomatchzzzz"


def test_validation_rules(tmp_path):
    good = make_doc(tmp_path)
    errors, _ = validate([good])
    assert errors == []

    unfinished = make_doc(tmp_path, status="verified", verified_by="h", _body="[[TO FILL]] and more text here to pass length")
    errors, _ = validate([unfinished])
    assert any("placeholders" in e for e in errors)

    bad_mail = make_doc(tmp_path, _body="Write to john.doe@gmail.com for details about this process.")
    errors, _ = validate([bad_mail])
    assert any("official domains" in e for e in errors)

    ok_mail = make_doc(tmp_path, _body="Write to admissions@ictuniversity.org for details about this process.")
    assert validate([ok_mail])[0] == []

    wrong_cat = make_doc(tmp_path, category="erp")
    assert any("stored under" in e for e in validate([wrong_cat])[0])

    unverified = make_doc(tmp_path, status="verified", verified_by=None)
    assert any("verified_by" in e for e in validate([unverified])[0])


def test_sheet_grouping_and_rendering():
    cfg = {
        "name": "t", "doc_id": "timetables-classes", "category": "timetables", "title": "Class timetable",
        "tier": "daily", "columns": ["Program", "Year", "Semester", "Course"],
        "group_by": ["Program", "Year", "Semester"], "rows_per_chunk": 2,
    }
    text = ("Program,Year,Semester,Course\nSoftware Engineering,Year 2,S1,Databases\n"
            "Software Engineering,Year 2,S1,Networks\nSoftware Engineering,Year 2,S1,Algorithms\n"
            "Cyber Security,Year 1,S2,Ethics\n,,,\n")
    headers, rows = sheets.parse_rows(text)
    docs = sheets.build_docs(cfg, headers, rows)
    ids = sorted(d.id for d in docs)
    assert ids == ["timetables-classes-cyber-security-year-1-s2", "timetables-classes-software-engineering-year-2-s1"]
    se = next(d for d in docs if "software" in d.id)
    assert len(se.chunks) == 2  # three rows, two per chunk
    assert "Course: Databases" in se.chunks[0].content
    assert matches("timetables-classes", se.id) and not matches("timetables-class", se.id)


def test_sheet_missing_column_is_rejected():
    cfg = {"name": "t", "doc_id": "x", "category": "canteen", "title": "T", "tier": "daily", "columns": ["Item", "Price"]}
    try:
        sheets.build_docs(cfg, ["Item"], [{"Item": "Rice"}])
    except ValueError as exc:
        assert "Price" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_web_conversion_and_classification():
    html = ('<div class="et_pb_section"><h2>Fees</h2><p>Pay <strong>early</strong>.</p>'
            '<script>alert(1)</script><table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></div>')
    md = web.html_to_markdown(html)
    assert "## Fees" in md and "alert" not in md and "| A | B |" in md.replace("  ", " ")
    cfg = web.load_config()
    assert web.classify(cfg, {"slug": "academic-calendar-2026-2027", "type": "page"})["category"] == "about"
    assert web.classify(cfg, {"slug": "masters-msc-in-artificial-intelligence-ai", "type": "page"})["category"] == "programs"
    assert web.classify(cfg, {"slug": "x", "type": "post"})["category"] == "announcements"
    assert web.infer_level("masters-msc-in-artificial-intelligence-ai", "") == ["masters"]
    assert web.infer_level("bachelors-of-science-bsc-in-cyber-security", "") == ["bachelor"]


def test_hash_embedder_is_deterministic_and_normalised():
    e = HashEmbedder()
    a, b = e.embed_query("pay fees in installments"), e.embed_documents(["pay fees in installments"])[0]
    assert a == b and abs(sum(x * x for x in a) - 1.0) < 1e-6
    assert len(a) == 1024


def test_catalog_is_consistent_with_golden_and_sheets():
    from ictkb.catalog import load_catalog
    from ictkb.evaluation import load_golden

    s = get_settings()
    catalog = load_catalog(s)
    ids = {e["id"] for e in catalog}
    sheet_names = {c["name"] for c in sheets.load_config(s)}
    assert {e["sheet"] for e in catalog if e["kind"] == "sheet"} == sheet_names
    for q in load_golden(s.root / "eval" / "golden_questions.yml"):
        for exp in q["expected_docs"]:
            assert exp in ids or exp.startswith("web-") or exp.removesuffix("-files") in ids, f"{q['id']} expects unknown document {exp}"
    golden_ids = {q["id"] for q in load_golden(s.root / "eval" / "golden_questions.yml")}
    for e in catalog:
        assert set(e["golden"]) <= golden_ids, e["id"]


def test_generated_stubs_validate():
    from ictkb.content import load_all

    errors, _ = validate(load_all())
    assert errors == []
    assert frontmatter  # imported for parity with the stub writer
