"""Generation of document stubs, sheet templates and the collection checklist from schema/catalog.yml."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import frontmatter

from .config import Settings, get_settings
from .connectors.sheets import load_config as load_sheets
from .connectors.sheets import template_csv
from .util import load_yaml, today

KIND_LABEL = {"D": "Document", "I": "Image", "S": "Spreadsheet", "Q": "Ask the office", "W": "Website"}
EXT_HINT = {"D": "pdf", "I": "jpg", "S": "xlsx"}


def load_catalog(settings: Settings | None = None) -> list[dict]:
    settings = settings or get_settings()
    entries = load_yaml(settings.schema_dir / "catalog.yml")
    seen: set[str] = set()
    for e in entries:
        if e["id"] in seen:
            raise ValueError(f"duplicate catalog id {e['id']}")
        seen.add(e["id"])
        e.setdefault("kind", "doc")
        e.setdefault("levels", ["all"])
        e.setdefault("asks", [])
        e.setdefault("give", [])
        e.setdefault("golden", [])
    return entries


def _split(item: str) -> tuple[str, str]:
    code, _, text = item.partition("|")
    return code.strip(), text.strip()


def write_stubs(settings: Settings | None = None, force: bool = False) -> tuple[list[str], list[str]]:
    """Create one draft Markdown stub per kind: doc entry. Existing files are kept unless force is set."""
    settings = settings or get_settings()
    created, skipped = [], []
    for e in load_catalog(settings):
        if e["kind"] != "doc":
            continue
        folder = settings.content_dir / e["category"]
        if e["category"] == "programs" and e["levels"] != ["all"]:
            folder = folder / e["levels"][0]
        path = folder / f"{e['id']}.md"
        if path.exists() and not force:
            skipped.append(e["id"])
            continue
        meta = {
            "id": e["id"], "title": e["title"], "category": e["category"], "subcategory": None,
            "program_level": e["levels"], "department": None, "language": "en",
            "source_type": "official_doc", "source_url": None, "attachments": [],
            "academic_year": None, "semester": None, "valid_from": None, "valid_until": None,
            "freshness_tier": e["tier"], "status": "draft", "last_verified": today().isoformat(),
            "verified_by": None, "owner": "unassigned", "collected_by": None, "collected_on": None,
            "confirmed_in_writing": False, "conflict_note": None, "tags": [], "related": [],
        }
        body = "\n\n".join(f"## {q}\n\n[[TO FILL]]" for q in e["asks"]) or "[[TO FILL]]"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter.dumps(frontmatter.Post(body, **meta), sort_keys=False) + "\n", encoding="utf-8")
        created.append(e["id"])
    return created, skipped


def write_sheet_templates(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    out = settings.root / "templates" / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    names = []
    for cfg in load_sheets(settings):
        (out / f"{cfg['name']}.csv").write_text(template_csv(cfg), encoding="utf-8", newline="")
        names.append(cfg["name"])
    return names


def checklist_rows(settings: Settings | None = None) -> dict[str, list[dict]]:
    """Return the upload rows, the sheet rows and the written-answer rows of the checklist."""
    settings = settings or get_settings()
    uploads, sheets, answers, asks_offices = [], [], [], []
    n = 0
    for e in load_catalog(settings):
        if e.get("covered_by"):
            continue
        topic = e["id"][len(e["category"]) + 1:]
        for item in e["give"]:
            code, text = _split(item)
            if code in ("D", "I"):
                n += 1
                uploads.append({
                    "no": n, "priority": e["prio"], "category": e["category"], "type": KIND_LABEL[code],
                    "item": text,
                    "file_name": f"incoming/{e['category']}/{e['category']}_{topic}_YYYY-MM-DD.{EXT_HINT[code]}",
                    "document": e["id"], "who": e["who"],
                })
            elif code == "Q":
                asks_offices.append({"priority": e["prio"], "category": e["category"], "item": text,
                                     "document": e["id"], "who": e["who"]})
        if e["kind"] == "sheet":
            sheets.append({"priority": e["prio"], "category": e["category"], "sheet": e["sheet"],
                           "template": f"templates/sheets/{e['sheet']}.csv", "document": e["id"], "who": e["who"],
                           "tier": e["tier"]})
        else:
            answers.append({"priority": e["prio"], "category": e["category"], "document": e["id"],
                            "path": f"content/{e['category']}/{e['id']}.md", "questions": len(e["asks"]),
                            "who": e["who"], "tier": e["tier"]})
    order = {"P0": 0, "P1": 1, "P2": 2}
    for rows in (uploads, sheets, answers, asks_offices):
        rows.sort(key=lambda r: (order[r["priority"]], r["category"]))
    for i, r in enumerate(uploads, 1):
        r["no"] = i
    return {"uploads": uploads, "sheets": sheets, "answers": answers, "asks": asks_offices}


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(lines)


def write_checklist(settings: Settings | None = None) -> list[Path]:
    settings = settings or get_settings()
    data = checklist_rows(settings)
    docs = settings.root / "docs"
    docs.mkdir(exist_ok=True)

    parts = [
        "# Collection checklist",
        "",
        "Generated from schema/catalog.yml by `ictkb scaffold`. Do not edit by hand; change the catalog instead.",
        "Priority P0 is needed for the core chatbot, P1 for a complete chatbot, P2 improves coverage.",
        "",
        f"## 1. Files to upload ({len(data['uploads'])})",
        "",
        "Place each file in the folder shown, replacing YYYY-MM-DD with the date the file was obtained. "
        "To add several files to one document, append a part label to the topic with a tilde, "
        "for example `programs_course-descriptions~software-engineering_2026-09-01.pdf`.",
        "",
        _md_table(["No", "Priority", "Category", "Type", "Item", "File name", "Maintainer"],
                  [[r["no"], r["priority"], r["category"], r["type"], r["item"], f"`{r['file_name']}`", r["who"]]
                   for r in data["uploads"]]),
        "",
        f"## 2. Google Sheets to fill ({len(data['sheets'])})",
        "",
        "Create one Google Sheet per row from the template, share it as \"Anyone with the link can view\", "
        "and put its id in sources/sheets.yml.",
        "",
        _md_table(["Priority", "Category", "Sheet", "Header template", "Update frequency", "Maintainer"],
                  [[r["priority"], r["category"], r["sheet"], f"`{r['template']}`", r["tier"], r["who"]]
                   for r in data["sheets"]]),
        "",
        f"## 3. Written answers ({len(data['answers'])} documents)",
        "",
        "Each stub lists its questions as headings. Replace every [[TO FILL]] with the verified answer, "
        "then set status to verified.",
        "",
        _md_table(["Priority", "Category", "Document", "Questions", "Update frequency", "Maintainer"],
                  [[r["priority"], r["category"], f"`{r['path']}`", r["questions"], r["tier"], r["who"]]
                   for r in data["answers"]]),
        "",
        f"## 4. Confirmations to obtain from offices ({len(data['asks'])})",
        "",
        _md_table(["Priority", "Category", "What to obtain", "For document", "Office"],
                  [[r["priority"], r["category"], r["item"], f"`{r['document']}`", r["who"]] for r in data["asks"]]),
        "",
    ]
    md_path = docs / "upload-checklist.md"
    md_path.write_text("\n".join(parts), encoding="utf-8")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["no", "priority", "category", "type", "item", "file_name", "document", "maintainer", "collected_by", "collected_on", "done"])
    for r in data["uploads"]:
        writer.writerow([r["no"], r["priority"], r["category"], r["type"], r["item"], r["file_name"],
                         r["document"], r["who"], "", "", ""])
    csv_path = docs / "upload-checklist.csv"
    csv_path.write_text(buffer.getvalue(), encoding="utf-8", newline="")
    return [md_path, csv_path]


def write_incoming_guides(settings: Settings | None = None) -> list[str]:
    """Create incoming/<category>/ with a README listing what to place there and the exact file names."""
    from .content import load_categories

    settings = settings or get_settings()
    cats = load_categories(settings)["categories"]
    data = checklist_rows(settings)
    done = []
    for cid, info in cats.items():
        folder = settings.incoming_dir / cid
        folder.mkdir(parents=True, exist_ok=True)
        rows = [r for r in data["uploads"] if r["category"] == cid]
        sheets_ = [r for r in data["sheets"] if r["category"] == cid]
        lines = [
            f"# incoming/{cid}: {info['label']}",
            "",
            info["description"] + ".",
            "",
            "Put the files listed below in this folder, then run `ictkb intake` from the repository root.",
            "Replace YYYY-MM-DD with the date you obtained the file. Keep the file name otherwise unchanged.",
            "For several files of the same kind, add a part label after the topic, for example "
            f"`{cid}_<topic>~second-file_YYYY-MM-DD.pdf`.",
            "",
            "## Files to place here",
            "",
        ]
        if rows:
            lines += [_md_table(["Priority", "Item", "File name", "From"],
                                [[r["priority"], r["item"], "`" + r["file_name"].split("/")[-1] + "`", r["who"]] for r in rows])]
        else:
            lines.append("No files are expected in this category.")
        if sheets_:
            lines += ["", "## Google Sheets for this category", ""]
            lines += [f"- `{r['sheet']}`: fill the template `{r['template']}` (priority {r['priority']}, {r['who']})." for r in sheets_]
        lines += ["", "Accepted: PDF, DOCX, XLSX, CSV, PNG, JPG. Convert .doc to .docx and .xls to .xlsx first. "
                  "Photographs must be sharp and readable. Never place files with personal data here.", ""]
        (folder / "README.md").write_text(chr(10).join(lines), encoding="utf-8")
        done.append(cid)
    return done
