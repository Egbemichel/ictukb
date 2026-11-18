# API reference (version 1)

Base URL: `https://ictkb-api.ictkb-api-worker.workers.dev`. (The self-hosted Python API also serves interactive documentation at `/docs`.) Every endpoint except `/v1/health` requires the header `X-API-Key`. Responses are JSON. A key exceeding its rate limit receives status 429 with a `Retry-After` header.

## POST /v1/search

Request:

```json
{
  "query": "Can I pay my fees in installments?",
  "top_k": 5,
  "filters": { "category": "finance", "program_level": "masters", "language": "en" }
}
```

`top_k` defaults to 5 (maximum 20). All filters are optional. Do not filter by `language` unless required: a French question may be answered by an English document.

Response:

```json
{
  "confidence": "high",
  "results": [
    {
      "chunk_id": 412,
      "text": "Paying tuition in installments | Can I pay in installments?\n\nYes. ...",
      "heading_path": "Can I pay in installments?",
      "score": 0.0328,
      "similarity": 0.71,
      "document": {
        "id": "finance-installments",
        "title": "Paying tuition in installments",
        "category": "finance",
        "source_url": null,
        "attachments": [{ "cloudinary_id": "...", "kind": "pdf", "description": "...", "url": "https://res.cloudinary.com/..." }],
        "last_verified": "2026-11-17",
        "freshness_tier": "semester",
        "status": "verified",
        "stale": false
      }
    }
  ]
}
```

`confidence` is `high`, `low` or `none`. When it is not `high`, a chatbot should say that it does not know and point to the relevant office. `stale: true` means the document is past its freshness limit; mention that the information may be out of date.

## GET /v1/documents/{id}

Returns the document metadata and its chunks in order. Status 404 when the document does not exist or is not indexed in this environment.

## GET /v1/documents

Query parameters: `category`, `limit` (default 50, maximum 200), `offset`.

## GET /v1/categories

Lists the 13 categories with their description and document count.

## GET /v1/freshness

Per category: document count, number of stale documents, and the time of the last content change.

## POST /v1/feedback

```json
{ "query": "...", "chunk_id": 412, "document_id": "finance-installments", "verdict": "wrong", "note": "The second installment date is outdated" }
```

`verdict` is one of `wrong`, `missing`, `outdated`, `helpful`. Feedback is stored for the maintainers; it never changes the index by itself.

## GET /v1/health

No key required. Returns status, version, environment, document and chunk counts, and the embedding model.

## Administration

Requires `X-Admin-Token`. Disabled when `ADMIN_TOKEN` is unset.

| Method and path | Effect |
|---|---|
| `POST /v1/admin/sync/sheet/{name}` | Synchronise one configured sheet in the background (status 202) |
| `POST /v1/admin/sync/website` | Re-read the website in the background |
| `POST /v1/admin/keys` | Create a key: `{"owner": "name", "rate_limit_per_min": 60}`. The key is returned once |
| `DELETE /v1/admin/keys/{id}` | Revoke a key |

## Recommended chatbot behaviour

1. Send the student's question to `/v1/search` without filters.
2. If `confidence` is `high`, give the retrieved text to the language model with an instruction to answer only from it, and cite `document.title` and `source_url`.
3. If `confidence` is `low` or `none`, answer that the information is not available and name the office that probably holds it.
4. Show `last_verified` for time-sensitive categories (finance, timetables, canteen, announcements).
5. Offer a way to report a wrong answer and send it to `/v1/feedback`.
