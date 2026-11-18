CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kb_meta (
  key   text PRIMARY KEY,
  value text NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  id                text PRIMARY KEY,
  title             text NOT NULL,
  category          text NOT NULL CHECK (category IN (
                      'about','admissions','programs','procedures','finance','erp','campus',
                      'transport','canteen','timetables','people','student-life','announcements')),
  subcategory       text,
  program_level     text[] NOT NULL DEFAULT '{all}',
  department        text,
  language          text NOT NULL DEFAULT 'en',
  source_type       text NOT NULL,
  source_url        text,
  attachments       jsonb NOT NULL DEFAULT '[]',
  academic_year     text,
  semester          text,
  valid_from        date,
  valid_until       date,
  freshness_tier    text NOT NULL CHECK (freshness_tier IN ('realtime','daily','semester','static')),
  status            text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','verified','deprecated')),
  last_verified     date NOT NULL,
  verified_by       text,
  owner             text NOT NULL,
  tags              text[] NOT NULL DEFAULT '{}',
  related           text[] NOT NULL DEFAULT '{}',
  origin            text NOT NULL DEFAULT 'git' CHECK (origin IN ('git','web','sheet')),
  origin_ref        text,
  max_age_days      int,
  content_hash      text NOT NULL,
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id            bigserial PRIMARY KEY,
  document_id   text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index   int NOT NULL,
  heading_path  text,
  source        text NOT NULL DEFAULT 'body',
  content       text NOT NULL,
  token_count   int,
  embedding     vector(1024),
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS documents_filter_idx ON documents (category, status, freshness_tier);
CREATE INDEX IF NOT EXISTS documents_origin_idx ON documents (origin, origin_ref);

CREATE TABLE IF NOT EXISTS api_keys (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner               text NOT NULL,
  key_hash            text NOT NULL UNIQUE,
  rate_limit_per_min  int,
  created_at          timestamptz NOT NULL DEFAULT now(),
  last_used_at        timestamptz,
  revoked_at          timestamptz
);

CREATE TABLE IF NOT EXISTS feedback (
  id           bigserial PRIMARY KEY,
  query        text,
  chunk_id     bigint,
  document_id  text,
  verdict      text NOT NULL CHECK (verdict IN ('wrong','missing','outdated','helpful')),
  note         text,
  api_key_id   uuid,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id            bigserial PRIMARY KEY,
  source        text NOT NULL,
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz,
  docs_changed  int,
  status        text,
  error         text
);
