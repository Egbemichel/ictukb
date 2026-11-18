# ICT University Knowledge Base

A shared, versioned knowledge base about ICT University and a retrieval API that student chatbots query. The repository holds the curated content, the ingestion pipeline, the API, the evaluation set and the deployment configuration.

## Architecture in brief

| Layer | Technology | Role |
|---|---|---|
| Curated content | Markdown with YAML front matter in `content/` | Stable information, reviewed through pull requests |
| Volatile data | Google Sheets, read by `ictkb sync-sheets` | Timetables, menu, announcements, directories |
| Website | WordPress REST API, read by `ictkb crawl` | Programs, admission pages, academic calendar, news |
| Files and images | Cloudinary, registered by `ictkb intake` | Originals; their extracted text is indexed |
| Index | PostgreSQL with pgvector (Neon) | Hybrid search: vector similarity and keyword match |
| API | Cloudflare Worker (free), with a FastAPI reference implementation | `POST /v1/search` and related read endpoints |
| Live feeds | WhatsApp listener (`whatsapp-listener/`) | Menu, bus and announcement posts from official admin groups |
| Automation | GitHub Actions | Validation, evaluation, scheduled ingestion, deployment |

The design is described in [docs/architecture.md](docs/architecture.md) and the endpoints in [docs/api.md](docs/api.md).

## Where to start

- Collecting data: read [docs/data-collection-guide.md](docs/data-collection-guide.md) and work through [docs/upload-checklist.md](docs/upload-checklist.md).
- Building a chatbot: copy [examples/starter-chatbot](examples/starter-chatbot) and request an API key from the maintainers.
- Operating and deploying: [docs/runbook.md](docs/runbook.md) and [docs/deployment.md](docs/deployment.md).
- Live API: `https://ictkb-api.ictkb-api-worker.workers.dev` (an API key is required; ask the maintainer).
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate            # on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                 # then edit the values
docker compose -f docker/docker-compose.yml up -d db
ictkb migrate
ictkb validate
ictkb index                          # indexes verified content (and drafts when KB_ENV=staging)
ictkb crawl                          # reads the university website
uvicorn ictkb.api.main:app --reload
```

Commands: `ictkb --help` lists `validate`, `migrate`, `index`, `crawl`, `sync-sheets`, `intake`, `reindex`, `freshness`, `keys`, `scaffold` and `search`.

## Tests and evaluation

```bash
pytest                                          # unit tests; integration tests need TEST_DATABASE_URL
TEST_DATABASE_URL=postgresql://ictkb:ictkb@localhost:5432/ictkb pytest
python eval/run_eval.py                         # golden questions against the configured index
```

The evaluation reports hit@5, mean reciprocal rank and no-answer correctness over the questions whose expected documents are already indexed, and reports coverage separately. Targets are 85 percent overall and 95 percent for P0 topics.

## Licence

MIT. See [LICENSE](LICENSE). The content describes a university; reuse of the content outside this project should respect the university's own copyright on its documents.
