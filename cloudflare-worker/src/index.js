// ICT University knowledge base API on a free Cloudflare Worker (reads Neon over HTTP).
import data from './data.json' with { type: 'json' };
import {
  EMBED_NAME, OFFICIAL_DOMAINS, buildTsQuery, chunkPost, db, deliveryUrl, detectLanguage, embed, isStale, safeEqual, sha256Hex, slugify,
  transaction, transcribe, vecLiteral,
} from './lib.js';

const VERSION = '0.1.0';
const KINDS = {
  'canteen-menu': { prefix: 'canteen-menu', category: 'canteen', title: 'Canteen menu', days: 0, daily: true },
  'bus-update': { prefix: 'transport-update', category: 'transport', title: 'Bus update', days: 7, daily: false },
  'student-life-post': { prefix: 'student-life-update', category: 'student-life', title: 'Student life update', days: 14, daily: false },
  announcement: { prefix: 'announcements-current-note', category: 'announcements', title: 'Announcement', days: 14, daily: false },
};

class HttpError extends Error {
  constructor(status, detail, headers = {}) {
    super(detail);
    this.status = status;
    this.headers = headers;
  }
}

const searchCache = new Map(); // identical questions within five minutes reuse the answer check
const keyCache = new Map(); // key hash -> { until, caller }
const hits = new Map(); // caller ident -> timestamps (per isolate; approximate)

function json(body, status = 200, env = {}, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...cors(env), ...extra },
  });
}

function cors(env) {
  return {
    'Access-Control-Allow-Origin': env.CORS_ORIGINS ?? '*',
    'Access-Control-Allow-Headers': 'X-API-Key, X-Admin-Token, Content-Type',
    'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
  };
}

async function authenticate(request, env, query, ctx) {
  const key = request.headers.get('X-API-Key');
  let caller;
  if (key) {
    const hash = await sha256Hex(key);
    const cached = keyCache.get(hash);
    if (cached && cached.until > Date.now()) caller = cached.caller;
    else {
      const [row] = await query('SELECT id::text AS id, owner, rate_limit_per_min FROM api_keys WHERE key_hash = $1 AND revoked_at IS NULL', [hash]);
      caller = row ? { id: row.id, ident: `key:${row.id}`, limit: row.rate_limit_per_min || Number(env.DEFAULT_RATE_LIMIT_PER_MIN ?? 60) } : null;
      keyCache.set(hash, { until: Date.now() + 60000, caller });
      if (row) ctx.waitUntil(query('UPDATE api_keys SET last_used_at = now() WHERE id = $1::uuid', [row.id]));
    }
    if (!caller) throw new HttpError(401, 'Invalid or revoked API key');
  } else if (String(env.REQUIRE_API_KEY ?? 'true') === 'true') {
    throw new HttpError(401, 'Missing X-API-Key header');
  } else {
    caller = { id: null, ident: `ip:${request.headers.get('CF-Connecting-IP') ?? 'unknown'}`, limit: Number(env.DEFAULT_RATE_LIMIT_PER_MIN ?? 60) };
  }
  const now = Date.now();
  const window = (hits.get(caller.ident) ?? []).filter((t) => now - t < 60000);
  if (window.length >= caller.limit) throw new HttpError(429, 'Rate limit exceeded', { 'Retry-After': '30' });
  window.push(now);
  hits.set(caller.ident, window);
  return caller;
}

function requireAdmin(request, env) {
  if (!env.ADMIN_TOKEN) throw new HttpError(503, 'Admin interface is disabled (ADMIN_TOKEN is not set)');
  if (!safeEqual(request.headers.get('X-Admin-Token') ?? '', env.ADMIN_TOKEN)) throw new HttpError(403, 'Invalid admin token');
}

async function body(request) {
  try {
    return await request.json();
  } catch {
    throw new HttpError(422, 'Body must be JSON');
  }
}

function statuses(env) {
  return String(env.KB_ENV ?? 'production') === 'production' ? ['verified'] : ['verified', 'draft'];
}

// ---------------------------------------------------------------- search
async function search(env, query, input) {
  const q = String(input.query ?? '').trim();
  if (q.length < 2 || q.length > 1000) throw new HttpError(422, 'query must be 2 to 1000 characters');
  const topK = Math.min(20, Math.max(1, Number(input.top_k ?? 5) || 5));
  const f = input.filters ?? {};
  const cacheKey = JSON.stringify([q.toLowerCase(), topK, input.filters ?? null, input.verify !== false]);
  const cached = searchCache.get(cacheKey);
  if (cached && cached.until > Date.now()) return cached.value;
  const [embedding] = await embed(env, [q]);
  const params = [vecLiteral(embedding), buildTsQuery(q), statuses(env), topK];
  const clauses = ['d.status = ANY($3::text[])', '(d.valid_until IS NULL OR d.valid_until >= current_date)'];
  if (f.category) { params.push(String(f.category)); clauses.push(`d.category = $${params.length}`); }
  if (f.language) { params.push(String(f.language)); clauses.push(`d.language = $${params.length}`); }
  if (f.program_level) { params.push(String(f.program_level)); clauses.push(`(d.program_level && ARRAY[$${params.length}, 'all']::text[])`); }
  const where = clauses.join(' AND ');
  const sql = `
    WITH cand_vec AS (
      SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> $1::vector) AS rnk
      FROM chunks c JOIN documents d ON d.id = c.document_id
      WHERE ${where} ORDER BY c.embedding <=> $1::vector LIMIT 40),
    cand_kw AS (
      SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, to_tsquery('simple', $2)) DESC) AS rnk
      FROM chunks c JOIN documents d ON d.id = c.document_id
      WHERE ${where} AND c.tsv @@ to_tsquery('simple', $2)
      ORDER BY ts_rank_cd(c.tsv, to_tsquery('simple', $2)) DESC LIMIT 40),
    fused AS (
      SELECT id, SUM(1.0 / (60 + rnk)) AS score
      FROM (SELECT id, rnk FROM cand_vec UNION ALL SELECT id, rnk FROM cand_kw) u GROUP BY id)
    SELECT f.score::float8 AS score, (1 - (c.embedding <=> $1::vector))::float8 AS similarity, c.id AS chunk_id,
           c.heading_path, c.content, d.id AS doc_id, d.title, d.category, d.source_url, d.attachments,
           d.last_verified::text AS last_verified, d.freshness_tier, d.max_age_days, d.status
    FROM fused f JOIN chunks c ON c.id = f.id JOIN documents d ON d.id = c.document_id
    ORDER BY f.score DESC, similarity DESC LIMIT $4`;
  const rows = await query(sql, params);
  if (!rows.length) return { confidence: 'none', verification: 'none', results: [] };
  const results = rows.map((r) => ({
    chunk_id: Number(r.chunk_id), text: r.content, heading_path: r.heading_path, score: r.score, similarity: r.similarity,
    document: {
      id: r.doc_id, title: r.title, category: r.category, source_url: r.source_url,
      attachments: (r.attachments ?? []).map((a) => ({ ...a, url: deliveryUrl(env, a.cloudinary_id, a.kind) })),
      last_verified: r.last_verified, freshness_tier: r.freshness_tier, status: r.status,
      stale: isStale(r.freshness_tier, r.last_verified, r.max_age_days),
    },
  }));
  const best = Math.max(...results.map((r) => r.similarity));
  const verdict = await verifyAnswer(env, q, best, results, input.verify !== false);
  const value = { confidence: verdict.confidence, verification: verdict.method, results };
  if (searchCache.size > 300) searchCache.clear();
  searchCache.set(cacheKey, { until: Date.now() + 300000, value });
  return value;
}

// Decides whether the retrieved passages actually answer the question. A very strong match is accepted and a very
// weak one is rejected without a model call; in between, a small language model answers YES or NO.
const STRONG_MATCH = 0.70;
const WEAK_MATCH = 0.45;
const DEFAULT_VERIFIER = '@cf/meta/llama-3.1-8b-instruct-fp8';

async function verifyAnswer(env, question, best, results, allowed) {
  const similarityOnly = { confidence: best >= Number(env.MIN_SIMILARITY ?? 0.4) ? 'high' : 'low', method: 'similarity' };
  if (!allowed || !env.AI || String(env.VERIFY_ENABLED ?? 'true') !== 'true') return similarityOnly;
  if (best >= STRONG_MATCH) return { confidence: 'high', method: 'strong-match' };
  if (best < WEAK_MATCH) return { confidence: 'low', method: 'weak-match' };
  try {
    const answer = await Promise.race([
      gradeWith(env, env.VERIFY_MODEL ?? DEFAULT_VERIFIER, question, results.slice(0, 3).map((r) => r.text)),
      new Promise((_, reject) => setTimeout(() => reject(new Error('verifier timeout')), 8000)),
    ]);
    return { confidence: /^\s*YES/i.test(answer) ? 'high' : 'low', method: 'model' };
  } catch {
    return { ...similarityOnly, method: 'fallback' };
  }
}

// ---------------------------------------------------------------- answer check
const GRADER_RULES = 'You check whether retrieved passages contain the answer to a question about ICT University. '
  + 'The question may be in English or French. Reply with exactly one word: YES or NO. '
  + 'Reply YES only if the passages state the specific information the question asks for. '
  + 'Reply NO if the passages are only about a related topic, if the question asks for personal or private data '
  + '(a person\'s balance, grades, private phone numbers), asks for something unrelated to the university (weather, news), '
  + 'or asks to predict a future result.';

async function gradeWith(env, model, question, passages) {
  const context = passages.map((p, i) => `Passage ${i + 1}:\n${p.slice(0, 900)}`).join('\n\n');
  const result = await env.AI.run(model, {
    messages: [
      { role: 'system', content: GRADER_RULES },
      { role: 'user', content: `${context}\n\nQuestion: ${question}\n\nDo the passages contain the answer? Reply YES or NO.` },
    ],
    max_tokens: 4, temperature: 0,
  });
  return String(result.response ?? result.choices?.[0]?.message?.content ?? '').trim();
}

// ---------------------------------------------------------------- documents and metadata
async function getDocument(env, query, id) {
  const [doc] = await query('SELECT *, last_verified::text AS lv, valid_from::text AS vf, valid_until::text AS vu, updated_at::text AS ua FROM documents WHERE id = $1 AND status = ANY($2::text[])', [id, statuses(env)]);
  if (!doc) throw new HttpError(404, 'Document not found');
  const chunks = await query('SELECT chunk_index, heading_path, content FROM chunks WHERE document_id = $1 ORDER BY chunk_index', [id]);
  return {
    id: doc.id, title: doc.title, category: doc.category, subcategory: doc.subcategory, program_level: doc.program_level,
    department: doc.department, language: doc.language, source_type: doc.source_type, source_url: doc.source_url,
    attachments: (doc.attachments ?? []).map((a) => ({ ...a, url: deliveryUrl(env, a.cloudinary_id, a.kind) })),
    academic_year: doc.academic_year, semester: doc.semester, valid_from: doc.vf, valid_until: doc.vu,
    freshness_tier: doc.freshness_tier, last_verified: doc.lv, stale: isStale(doc.freshness_tier, doc.lv, doc.max_age_days),
    tags: doc.tags, related: doc.related, updated_at: doc.ua, chunks,
  };
}

async function categoryReport(env, query) {
  const rows = await query('SELECT category, freshness_tier, last_verified::text AS lv, max_age_days, updated_at::text AS ua FROM documents WHERE status = ANY($1::text[])', [statuses(env)]);
  const report = {};
  for (const r of rows) {
    const e = (report[r.category] ??= { category: r.category, documents: 0, stale: 0, last_update: null });
    e.documents += 1;
    if (isStale(r.freshness_tier, r.lv, r.max_age_days)) e.stale += 1;
    if (!e.last_update || r.ua > e.last_update) e.last_update = r.ua;
  }
  return Object.values(report).sort((a, b) => a.category.localeCompare(b.category));
}

// ---------------------------------------------------------------- posts (menu, bus, announcements)
function checkText(text) {
  const t = String(text ?? '').trim();
  if (t.length < 5) throw new HttpError(422, 'The text is empty');
  if (t.length > 6000) throw new HttpError(422, 'The text is longer than 6000 characters');
  for (const m of t.matchAll(/[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)/g)) {
    if (!OFFICIAL_DOMAINS.includes(m[1].toLowerCase())) throw new HttpError(422, `Email address outside the official domains: ${m[0]}`);
  }
  return t;
}

async function postNote(env, query, input) {
  const spec = KINDS[input.kind];
  if (!spec) throw new HttpError(422, `Unknown kind. Use one of: ${Object.keys(KINDS).join(', ')}`);
  const by = String(input.by ?? '').trim();
  if (by.length < 2 || by.length > 60) throw new HttpError(422, 'by must be 2 to 60 characters');
  const text = checkText(input.text);
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  const on = input.date && iso.test(input.date) ? input.date : new Date().toISOString().slice(0, 10);
  const until = input.until && iso.test(input.until) ? input.until
    : new Date(Date.parse(`${on}T00:00:00Z`) + spec.days * 86400000).toISOString().slice(0, 10);
  const label = input.title ? String(input.title).trim() : spec.title;
  let id; let title;
  if (spec.daily) { id = `${spec.prefix}-${on}`; title = `${spec.title} for ${on}`; } else {
    const suffix = input.key ? slugify(String(input.key)).slice(0, 60) : (input.title ? slugify(String(input.title)).slice(0, 40) : 'post');
    id = `${spec.prefix}-${on}-${suffix}`; title = `${label} (${on})`;
  }
  const chunks = chunkPost(title, `## ${title}\n\n${text}`.split('\n\n').slice(1).join('\n\n') || text);
  const [model] = await query("SELECT value FROM kb_meta WHERE key = 'embedding_model'");
  const expected = EMBED_NAME;
  if (model && model.value !== expected) throw new HttpError(409, `The index uses ${model.value}; reindex before posting`);
  const vectors = await embed(env, chunks.map((c) => c.content));
  const hash = await sha256Hex(title + chunks.map((c) => c.content).join('\u001e'));
  const maxAge = Math.max(1, Math.round((Date.parse(until) - Date.parse(on)) / 86400000) + 1);
  const statements = [
    [`INSERT INTO documents (id, title, category, subcategory, program_level, language, source_type, attachments, freshness_tier, status,
        last_verified, verified_by, owner, tags, related, origin, origin_ref, max_age_days, valid_from, valid_until, content_hash, updated_at)
      VALUES ($1,$2,$3,$4,'{all}',$5,'observation','[]','realtime','verified',current_date,$6,$6,$7,'{}','note',$4,$8,$9::date,$10::date,$11,now())
      ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, language=EXCLUDED.language, last_verified=current_date, verified_by=EXCLUDED.verified_by,
        owner=EXCLUDED.owner, max_age_days=EXCLUDED.max_age_days, valid_from=EXCLUDED.valid_from, valid_until=EXCLUDED.valid_until,
        content_hash=EXCLUDED.content_hash, updated_at=now()`,
      [id, title, spec.category, input.kind, detectLanguage(text), by, [input.kind], maxAge, on, until, hash]],
    ['DELETE FROM chunks WHERE document_id = $1', [id]],
    ...chunks.map((c, i) => [
      'INSERT INTO chunks (document_id, chunk_index, heading_path, source, content, token_count, embedding) VALUES ($1,$2,$3,$4,$5,$6,$7::vector)',
      [id, i, c.heading, 'body', c.content, Math.ceil(c.content.length / 4), vecLiteral(vectors[i])]]),
  ];
  await transaction(env, statements);
  return { id };
}

// ---------------------------------------------------------------- router
async function route(request, env, ctx) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, '') || '/';
  const method = request.method;
  const query = db(env);

  if (method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(env) });
  if (path === '/' || path === '/v1') return json({ name: 'ICT University knowledge base API', version: VERSION, docs: '/v1/health' }, 200, env);

  if (path === '/v1/health' && method === 'GET') {
    const [counts] = await query('SELECT (SELECT count(*) FROM documents)::int AS documents, (SELECT count(*) FROM chunks)::int AS chunks');
    const [model] = await query("SELECT value FROM kb_meta WHERE key = 'embedding_model'");
    return json({ status: 'ok', version: VERSION, environment: env.KB_ENV, runtime: 'cloudflare-worker', ...counts, embedding_model: model?.value ?? null }, 200, env);
  }

  if (path.startsWith('/v1/admin/')) {
    requireAdmin(request, env);
    if (path === '/v1/admin/notes' && method === 'POST') return json(await postNote(env, query, await body(request)), 201, env);
    if (path.startsWith('/v1/admin/notes/') && method === 'DELETE') {
      const id = decodeURIComponent(path.slice('/v1/admin/notes/'.length));
      const rows = await query("DELETE FROM documents WHERE id = $1 AND origin = 'note' RETURNING id", [id]);
      if (!rows.length) throw new HttpError(404, 'Post not found');
      return json({ deleted: id }, 200, env);
    }
    if (path === '/v1/admin/transcribe' && method === 'POST') {
      const b = await body(request);
      if (!/^image\/(jpeg|png|webp)$/.test(b.mime ?? 'image/jpeg') || typeof b.image_base64 !== 'string' || b.image_base64.length < 20) throw new HttpError(422, 'Invalid image');
      return json({ text: await transcribe(env, b.image_base64, b.mime ?? 'image/jpeg', b.kind ?? '') }, 200, env);
    }
    if (path === '/v1/admin/wa-state/get' && method === 'POST') {
      const b = await body(request);
      const keys = (Array.isArray(b.keys) ? b.keys : []).slice(0, 500).map(String);
      const rows = keys.length ? await query('SELECT key, value FROM wa_state WHERE key = ANY($1::text[])', [keys]) : [];
      return json({ values: Object.fromEntries(rows.map((r) => [r.key, r.value])) }, 200, env);
    }
    if (path === '/v1/admin/wa-state/set' && method === 'POST') {
      const b = await body(request);
      const entries = Object.entries(b.entries && typeof b.entries === 'object' ? b.entries : {});
      if (entries.length > 500) throw new HttpError(422, 'At most 500 entries per request');
      const statements = entries.map(([key, value]) => (value === null
        ? ['DELETE FROM wa_state WHERE key = $1', [key]]
        : ['INSERT INTO wa_state (key, value, updated_at) VALUES ($1, $2, now()) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()', [key, String(value)]]));
      if (statements.length) await transaction(env, statements);
      return json({ stored: statements.length }, 200, env);
    }
    if (path === '/v1/admin/embed' && method === 'POST') {
      const b = await body(request);
      const texts = Array.isArray(b.texts) ? b.texts.map((x) => String(x).slice(0, 6000)) : [];
      if (!texts.length || texts.length > 100) throw new HttpError(422, 'Send between 1 and 100 texts');
      return json({ model: EMBED_NAME, embeddings: await embed(env, texts) }, 200, env);
    }
    if (path === '/v1/admin/keys' && method === 'POST') {
      const b = await body(request);
      if (!b.owner || String(b.owner).length < 2) throw new HttpError(422, 'owner is required');
      const bytes = crypto.getRandomValues(new Uint8Array(32));
      const key = `ictkb_${btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')}`;
      const [row] = await query('INSERT INTO api_keys (owner, key_hash, rate_limit_per_min) VALUES ($1, $2, $3) RETURNING id::text AS id', [String(b.owner), await sha256Hex(key), b.rate_limit_per_min ?? null]);
      return json({ id: row.id, owner: b.owner, api_key: key }, 201, env);
    }
    if (path.startsWith('/v1/admin/keys/') && method === 'DELETE') {
      const id = path.slice('/v1/admin/keys/'.length);
      const rows = await query('UPDATE api_keys SET revoked_at = now() WHERE id = $1::uuid AND revoked_at IS NULL RETURNING id', [id]).catch(() => []);
      if (!rows.length) throw new HttpError(404, 'Key not found or already revoked');
      keyCache.clear();
      return json({ revoked: id }, 200, env);
    }
    throw new HttpError(404, 'Not found');
  }

  if (path.startsWith('/v1/')) {
    const caller = await authenticate(request, env, query, ctx);
    if (path === '/v1/search' && method === 'POST') return json(await search(env, query, await body(request)), 200, env);
    if (path === '/v1/categories' && method === 'GET') {
      const counts = Object.fromEntries((await categoryReport(env, query)).map((c) => [c.category, c.documents]));
      return json({ categories: Object.entries(data.categories).map(([id, c]) => ({ id, label: c.label, description: c.description, documents: counts[id] ?? 0 })) }, 200, env);
    }
    if (path === '/v1/freshness' && method === 'GET') return json({ categories: await categoryReport(env, query) }, 200, env);
    if (path === '/v1/documents' && method === 'GET') {
      const limit = Math.min(200, Math.max(1, Number(url.searchParams.get('limit') ?? 50) || 50));
      const offset = Math.max(0, Number(url.searchParams.get('offset') ?? 0) || 0);
      const category = url.searchParams.get('category');
      const rows = await query(`SELECT id, title, category, freshness_tier, last_verified::text AS last_verified FROM documents WHERE status = ANY($1::text[]) ${category ? 'AND category = $4' : ''} ORDER BY category, id LIMIT $2 OFFSET $3`, category ? [statuses(env), limit, offset, category] : [statuses(env), limit, offset]);
      return json({ documents: rows, limit, offset }, 200, env);
    }
    if (path.startsWith('/v1/documents/') && method === 'GET') return json(await getDocument(env, query, decodeURIComponent(path.slice('/v1/documents/'.length))), 200, env);
    if (path === '/v1/feedback' && method === 'POST') {
      const b = await body(request);
      if (!['wrong', 'missing', 'outdated', 'helpful'].includes(b.verdict)) throw new HttpError(422, 'verdict must be wrong, missing, outdated or helpful');
      const [row] = await query('INSERT INTO feedback (query, chunk_id, document_id, verdict, note, api_key_id) VALUES ($1,$2,$3,$4,$5,$6::uuid) RETURNING id',
        [b.query?.slice(0, 1000) ?? null, b.chunk_id ?? null, b.document_id ?? null, b.verdict, b.note?.slice(0, 2000) ?? null, caller.id]);
      return json({ id: Number(row.id) }, 201, env);
    }
  }
  throw new HttpError(404, 'Not found');
}

export default {
  // Cron trigger: keeps a free-tier listener host awake by calling its health address.
  async scheduled(event, env, ctx) {
    if (env.LISTENER_URL) ctx.waitUntil(fetch(env.LISTENER_URL, { headers: { 'User-Agent': 'ictkb-keepalive' } }).catch(() => {}));
  },
  async fetch(request, env, ctx) {
    try {
      return await route(request, env, ctx);
    } catch (error) {
      if (error instanceof HttpError) return json({ detail: error.message }, error.status, env, error.headers);
      console.error(error);
      const admin = env.ADMIN_TOKEN && safeEqual(request.headers.get('X-Admin-Token') ?? '', env.ADMIN_TOKEN);
      return json({ detail: admin ? `Internal error: ${String(error.message).replace(/postgres(ql)?:\/\/\S+/g, '[connection string removed]')}` : 'Internal error' }, 500, env);
    }
  },
};

export { buildTsQuery, chunkPost, checkText };
