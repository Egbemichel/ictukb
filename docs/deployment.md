# Deployment

The public API runs on a free Cloudflare Worker (`cloudflare-worker/`). It reads the Neon database over HTTP, embeds queries with Workers AI (`@cf/baai/bge-m3`), and serves the same endpoints as the Python API (see [api.md](api.md)). Indexing (website crawl, sheets, content, private documents) stays in the Python pipeline, run from a maintainer's machine or from GitHub Actions.

```
students' chatbots --> Cloudflare Worker (free) --> Neon (Postgres + pgvector)
                              ^                         ^
WhatsApp listener ------------+           ictkb (Python): index, crawl, sync-sheets
```

Live address: `https://ictkb-api.ictkb-api-worker.workers.dev`

## Why a Worker and not the Python server

Cloudflare Workers cannot run the Python server (it needs a native Postgres driver). Cloudflare Containers can, but they require the paid Workers plan. The Worker is a JavaScript implementation of the read endpoints and of the post endpoints used by the WhatsApp listener. The Python API (`ictkb.api.main`) remains in the repository for self-hosting (`docker/Dockerfile.api`) and as the reference implementation; both share the same database.

Free plan limits to keep in mind: 100,000 requests per day, 10 ms of CPU per request (the waiting time for the database and the AI models does not count). The in-memory rate limiter is per Worker instance, so the effective limit is approximate; add a Cloudflare rate limiting rule for hard limits.

## Deploy or update

```bash
cd cloudflare-worker
npm install
npx wrangler login                       # once; authorise in the browser
python ../scripts/build_worker_data.py   # regenerates src/data.json from schema/categories.yml
npx wrangler secret put DATABASE_URL     # Neon connection string, without quotes
npx wrangler secret put COHERE_API_KEY   # used to transcribe menu images posted by the WhatsApp listener
npx wrangler secret put ADMIN_TOKEN      # long random string
npx wrangler deploy
```

Values in `wrangler.toml` (`KB_ENV`, `MIN_SIMILARITY`, `CLOUDINARY_CLOUD_NAME`, `CORS_ORIGINS`, ...) are not secret. When pasting secrets, remove quotes and trailing line breaks; a quoted `DATABASE_URL` is rejected by the driver.

Local test: put the same three values in `cloudflare-worker/.dev.vars` (git-ignored) and run `npx wrangler dev`.

## Automatic deployment

`.github/workflows/deploy.yml` deploys the Worker on every push to `main` and re-indexes the public content. Required repository secrets: `CLOUDFLARE_API_TOKEN` (template "Edit Cloudflare Workers"), `CLOUDFLARE_ACCOUNT_ID`, `DATABASE_URL`, `ADMIN_TOKEN` (indexing embeds through the Worker). The Worker's own secrets are stored in Cloudflare and are not touched by the workflow.

## API keys

Reads require an `X-API-Key`. Create one with the admin token:

```bash
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/admin/keys \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"owner": "student-name", "rate_limit_per_min": 60}'
```

The key is shown once. Revoke with `DELETE /v1/admin/keys/{id}`.

## Verification after deployment

```bash
curl https://ictkb-api.ictkb-api-worker.workers.dev/v1/health
curl -X POST https://ictkb-api.ictkb-api-worker.workers.dev/v1/search \
  -H "X-API-Key: KEY" -H "Content-Type: application/json" -d '{"query": "how do I apply"}'
python eval/run_eval.py
```

## Self-hosting the Python API

`docker compose -f docker/docker-compose.yml up -d db api` runs a local PostgreSQL, the Python API and, with `--profile whatsapp`, the WhatsApp listener. Any container host works for the image built from `docker/Dockerfile.api`.

## WhatsApp listener

The listener keeps a WhatsApp connection open, so it cannot run on a Worker. Its session is stored in Neon (through the Worker), which lets it run on a free host that restarts or sleeps: Render or a Hugging Face Space. The Worker's cron trigger pings the host every 5 minutes to keep it awake (`LISTENER_URL` in `wrangler.toml`). See `whatsapp-listener/README.md` for linking and hosting steps.

## Enabling the scheduled workflows

The scheduled and deployment workflows (`ingest-daily`, `ingest-live`, `deploy`) are switched off until the repository variable `ENABLE_AUTOMATION` is set to `true` (Settings, Secrets and variables, Actions, Variables). Add the secrets `DATABASE_URL`, `ADMIN_TOKEN`, `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` first. The `validate` workflow and the daily `freshness` workflow run without them.
