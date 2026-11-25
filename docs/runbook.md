# Runbook

## 1. One-time setup (infrastructure owner)

| Step | Action |
|---|---|
| 1 | Create the GitHub repository and push this project. Run `scripts/protect_main.sh OWNER/REPO` after replacing the placeholders in `.github/CODEOWNERS`. |
| 2 | `neon init` and `neon deploy` link the repository to the Neon project and write DATABASE_URL (pooled) and the object storage variables to `.env.local`, which the tools read before `.env`. Create a Neon project. Enable the `vector` extension (the first migration does it). Copy the pooled connection string. Create a second branch for staging if desired. |
| 3 | Deploy the Cloudflare Worker (see [deployment.md](deployment.md)) and set its `ADMIN_TOKEN`; the default `EMBEDDING_PROVIDER=worker` embeds through it. Set `EMBEDDING_PROVIDER=fastembed` for a local model instead. |
| 4 | Create a Cloudinary account and copy the cloud name, API key and API secret. |
| 5 | Add the repository secrets: `DATABASE_URL`, `ADMIN_TOKEN`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, and optionally `DEPLOY_HOOK_URL`. |
| 6 | Run `ictkb migrate` once with the production `DATABASE_URL`. |
| 7 | Run `ictkb scaffold` if the stubs are missing, then start collection. |
| 8 | Deploy the API image (see [deployment.md](deployment.md)). |
| 9 | Create the first keys: `ictkb keys create --owner student-name`. |

## 2. Routine operations

| Task | Command |
|---|---|
| Validate content | `ictkb validate` |
| Index content | `ictkb index` (production indexes only verified documents) |
| Read the website | `ictkb crawl` or `ictkb crawl --dry-run --out data/web-snapshot` |
| Sync sheets | `ictkb sync-sheets [--tier realtime] [--name canteen-menu]` |
| Register collected files | `ictkb intake` |
| Stale documents | `ictkb freshness [--db] [--json]` |
| Retrieval quality | `python eval/run_eval.py [--strict]` |
| Try a query | `ictkb search "how do I pay in installments"` |
| Issue a key | `ictkb keys create --owner NAME [--rate-limit 120]` |
| List or revoke keys | `ictkb keys list`, `ictkb keys revoke KEY_ID` |

## 3. Scheduled jobs

| Workflow | Schedule | Effect |
|---|---|---|
| ingest-live | every 15 minutes | realtime sheets |
| ingest-daily | 03:00 UTC | website, daily, semester and static sheets |
| freshness | 06:30 UTC | one issue per stale document |
| deploy | push to main | migrate, index verified content, build and push the API image |

## 4. Incidents

| Symptom | Likely cause and action |
|---|---|
| Chatbot returns outdated information | Check `GET /v1/freshness`, then the owner's open stale issue. Re-verify and merge. |
| A sheet change does not appear | Check the sheet is shared by link, then run `ictkb sync-sheets --name NAME`. Read the last `ingestion_runs` rows. |
| A sync reports "refusing to delete" | The sheet or crawl returned nothing; fix the source, nothing was deleted. |
| Indexing stops with "built with another model" | The embedding model changed. Run `ictkb reindex`. |
| A bot misbehaves | `ictkb keys revoke KEY_ID`. The cache lasts up to 60 seconds per instance. |
| Search quality dropped | Run `python eval/run_eval.py`, read the failures, then adjust the headings or content of the failing documents. |
| 429 from the API | Raise the key limit with a new key and `--rate-limit`, or add caching in the chatbot. |

## 5. Backup and recovery

Content is in Git; sheets are in Google; files are in Cloudinary. The index can always be rebuilt: `ictkb migrate`, `ictkb index`, `ictkb crawl`, `ictkb sync-sheets`. Only API keys and feedback exist solely in the database; Neon point-in-time restore covers them.

## 6. Changing the embedding model

Set `EMBEDDING_PROVIDER` or `EMBEDDING_MODEL`, run `ictkb reindex` (the dimension must stay 1024), then run the evaluation and recalibrate `MIN_SIMILARITY`.

## 7. Daily posts

Menu, bus and announcement messages from WhatsApp are posted with `ictkb post` or `POST /v1/admin/notes` (see the data collection guide, section 6). `ictkb notes-prune` removes expired posts; it runs in the daily workflow.
