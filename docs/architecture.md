# Architecture

## 1. Data flow

```
 content/*.md (Git)  ---- ictkb index ------\
 incoming/ files ---- ictkb intake ---------+--> documents + chunks (PostgreSQL, pgvector) --> FastAPI --> chatbots
 Google Sheets   ---- ictkb sync-sheets ----+
 WordPress site  ---- ictkb crawl ----------/
```

Every path ends in the same two tables. A document is a unit with metadata; a chunk is a retrievable passage of a document with its embedding and a full-text vector. The `origin` column (`git`, `sheet`, `web`) records which path produced a document, so that each path removes only the orphans it owns.

## 2. Why content is split between Git and sheets

Stable content (procedures, policies, fee schedules) is reviewed in pull requests, versioned and attributable. Volatile content (menu, timetables, announcements) changes too often for pull requests, so it lives in Google Sheets that its maintainers already know how to edit, and is synchronised into the index. Each sheet is rendered into self-contained rows ("Day: Monday | Item: Rice | Price XAF: 500") so that a chunk is meaningful when retrieved alone.

## 3. Freshness

| Tier | Limit for last_verified | Typical content | Update path |
|---|---|---|---|
| realtime | 1 day | menu, announcements | sheet webhook, 15-minute schedule |
| daily | 7 days | timetables, events, news, ERP release notes | daily job |
| semester | 120 days | procedures, fees, regulations | pull request |
| static | 365 days | history, floor plans | pull request |

For Git documents, `last_verified` is set by a human. For sheet documents it is the date the sheet content last changed, so an unmaintained sheet becomes stale. For website pages it is the crawl date. The `max_age_days` field in `sources/sheets.yml` overrides the tier limit. `ictkb freshness` and the daily `freshness` workflow list stale documents and open one issue per document, assigned to its owner. The API exposes the same information (`stale` on each result and `GET /v1/freshness`) so that a chatbot can warn students that a piece of information may be out of date.

## 4. Retrieval

1. The query is embedded with the configured model (`input_type=search_query`).
2. Two candidate lists of 40 chunks are produced: nearest neighbours by cosine distance (HNSW index) and keyword matches (`tsvector` with an OR query of the informative words).
3. The lists are merged by reciprocal rank fusion with constant 60.
4. The top `top_k` chunks are returned with their document metadata.

Filters (`category`, `program_level`, `language`) apply to both lists. A document with `program_level: [all]` matches every level filter. Documents past `valid_until` are never returned. In production only `status: verified` documents exist in the index; in staging drafts are indexed too.

Each response carries `confidence`: `high` when the best chunk has cosine similarity of at least `MIN_SIMILARITY`, `low` when results exist but none reaches it, `none` when nothing matched. Chatbots should answer "I do not know" on `low` and `none`. Calibrate `MIN_SIMILARITY` with the evaluation report, which prints the lowest similarity among correctly answered questions and the highest among no-answer questions.

## 5. Embeddings

The schema fixes 1024 dimensions. The default provider is `worker`: Cloudflare Workers AI `@cf/baai/bge-m3`, reached through the deployed Worker with the admin token, which handles English and French and also embeds the live API's queries. `cohere` (`embed-multilingual-v3.0`) remains available. `fastembed` runs `multilingual-e5-large` locally without an API key; its vectors are not comparable with bge-m3, so a fastembed index is a separate local index. The `hash` provider exists for automated tests only. The model name is stored in `kb_meta`; the indexer refuses to mix models and `ictkb reindex` re-embeds every chunk after a change.

## 6. Chunking

Markdown is split at headings; each chunk carries the document title and heading path as a first line. Paragraphs are packed up to about 380 tokens. Tables are split by rows with the header repeated in each piece. Attachments contribute a chunk with their human-written description plus the chunks of their extracted text (stored under `content/<category>/_extracted/`, reviewable in pull requests).

## 7. Access control

| Surface | Credential | Purpose |
|---|---|---|
| `GET /v1/health` | none | liveness |
| search, documents, categories, freshness, feedback | `X-API-Key` | read access, per-key rate limit, revocation |
| `/v1/admin/*` | `X-Admin-Token` | trigger syncs, manage keys; no free-form writes |

Keys are stored as SHA-256 hashes. The rate limit is applied per key in process memory; place Cloudflare rate limiting in front for protection across instances.

## 8. Decisions and limits

- Cloudflare support for running Python directly (Python Workers, Containers) changes frequently. The API is delivered as a Docker image that runs on any small host, with Cloudflare used in front for DNS, caching and rate limiting. Verify current Cloudflare capabilities before moving the API onto it.
- GitHub Actions schedules can be delayed. Use the Apps Script webhook (`scripts/apps_script_webhook.gs`) for data that must be current within seconds.
- Text extraction covers PDF with a text layer, DOCX, XLSX, CSV and, with Tesseract installed, images. Scanned PDFs yield no text; supply a text version or a description.
- The shared in-process rate limiter and key cache are per instance. Running several instances multiplies the effective limit.
