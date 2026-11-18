# Contributing

## Principles

1. The repository is public and Git history is permanent. Commit official contact details only (office emails and office numbers). Never commit personal phone numbers or private email addresses of delegates, staff or club leaders unless that person has agreed in writing. Never commit secrets. `ictkb validate` rejects email addresses outside the official domains, and CI scans for credentials.
2. No sensitive data is stored. There are no audience tags: every document is available to every chatbot. Do not add personal records (grades, balances, identity numbers). The one exception is `contributors.yml`, where each contributor enters their own name and matricule with their consent.
3. Reads are open to everyone, but they require an API key. Keys exist for rate limiting and to disable a misbehaving chatbot, not for secrecy. Writes happen only through the pipeline with administrator credentials.
4. The office or the official document wins. If the website and an office disagree, use the office's information and record the disagreement in `conflict_note`.

## Workflow

1. Create a branch. Direct pushes to `main` are blocked.
2. Add or edit documents in `content/<category>/`, or place collected files in `incoming/<category>/` and run `ictkb intake`.
3. Run `ictkb validate`. It checks the schema, file names, categories, placeholders, email domains and attachment references.
4. Add yourself to `contributors.yml` (name, matricule, GitHub login, one sentence) and run `python scripts/build_contributors.py`. CI rejects a pull request whose author is not listed.
5. Open a pull request using the template. At least one code owner of the category must approve, and every check must pass.
6. When a pull request changes `content/`, CI indexes it into a throwaway staging index and runs the golden questions.

## Writing a document

- The file name equals the `id` and lives in the folder of its `category`.
- The front matter follows `schema/document.schema.json`. Start from the stub that `ictkb scaffold` generated.
- Put each answer under a heading phrased as the question a student would ask. Retrieval uses the heading path, so a precise heading improves results.
- State facts with their conditions: who, when, how much, which office, how long.
- A document is indexed in production only when `status: verified`. Replace every `[[TO FILL]]` first, set `verified_by` to your GitHub handle and `last_verified` to the date you checked it.
- `freshness_tier` sets how often it must be re-verified: `realtime` one day, `daily` seven days, `semester` 120 days, `static` 365 days. Stale documents open an issue for the owner.

## Naming collected files

`incoming/<category>/<category>_<topic>_YYYY-MM-DD.<ext>`, for example `incoming/finance/finance_fee-schedule_2026-09-01.pdf`. The category and topic select the document (`finance-fee-schedule`). To add several files to one document, append a part label to the topic with a tilde: `programs_course-descriptions~software-engineering_2026-09-01.pdf`.

Accepted types: PDF, DOCX, XLSX, CSV, and common image formats. Convert `.doc` to `.docx` and `.xls` to `.xlsx` first. Photographs must be sharp and readable. ERP screenshots are one file per step, numbered in order.

## Code changes

Changes under `src/`, `db/`, `docker/`, `.github/`, `schema/` and `eval/` need the infrastructure owner's approval. Add or update tests, run `ruff check src tests eval scripts` and `pytest`.

## Reporting problems

Use the issue templates: wrong answer, missing information, stale content.
