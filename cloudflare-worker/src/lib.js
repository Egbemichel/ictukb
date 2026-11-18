// Shared helpers: database, embeddings, text processing. Mirrors src/ictkb (the Python pipeline).
import { neon } from '@neondatabase/serverless';
import data from './data.json' with { type: 'json' };

export const LIMITS = { realtime: 1, daily: 7, semester: 120, static: 365, ...data.freshness_tiers };
export const OFFICIAL_DOMAINS = (data.allowed_email_domains ?? []).map((d) => d.toLowerCase());

const STOPWORDS = new Set((
  'the and for are how what when where who can does do is my you your with that this from have will any there which '
  + 'les des une est sont pour dans que qui quels quel quelle comment puis aux par sur vous nous mes mon ses'
).split(' '));

export function db(env) {
  const sql = neon(env.DATABASE_URL);
  return (text, params = []) => sql.query(text, params);
}

export async function transaction(env, statements) {
  const sql = neon(env.DATABASE_URL);
  return sql.transaction((txn) => statements.map(([text, params]) => txn.query(text, params)));
}

export function tier(tierName, maxAge) {
  return maxAge || LIMITS[tierName] || 365;
}

export function isStale(tierName, lastVerified, maxAge, now = new Date()) {
  const days = (now - new Date(`${lastVerified}T00:00:00Z`)) / 86400000;
  return days > tier(tierName, maxAge);
}

export function buildTsQuery(text) {
  const seen = [];
  for (const t of (text.toLowerCase().match(/[\p{L}\p{N}_]+/gu) ?? [])) {
    if (t.length > 2 && !STOPWORDS.has(t) && !seen.includes(t)) seen.push(t);
  }
  return seen.length ? seen.slice(0, 24).join(' | ') : 'zzzznomatchzzzz';
}

export const vecLiteral = (v) => `[${v.map((x) => Number(x).toPrecision(7)).join(',')}]`;

async function retryFetch(url, init, attempts = 4) {
  let last;
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(url, init);
      if (response.status === 429 || response.status >= 500) {
        last = new Error(`HTTP ${response.status}`);
        await new Promise((r) => setTimeout(r, 500 * 2 ** i));
        continue;
      }
      return response;
    } catch (error) {
      last = error;
      await new Promise((r) => setTimeout(r, 500 * 2 ** i));
    }
  }
  throw last;
}

export const EMBED_MODEL = '@cf/baai/bge-m3';
export const EMBED_NAME = `cloudflare:${EMBED_MODEL}`;

// Multilingual 1024-dimension embeddings from Workers AI (no monthly call limit; the daily free allowance is ample).
export async function embed(env, texts) {
  const out = [];
  for (let i = 0; i < texts.length; i += 50) {
    const result = await env.AI.run(EMBED_MODEL, { text: texts.slice(i, i + 50) });
    if (!result?.data || result.data.length !== texts.slice(i, i + 50).length) throw new Error('Embedding service returned an unexpected result');
    out.push(...result.data);
  }
  return out;
}

export async function transcribe(env, base64, mime, kind) {
  const hint = kind === 'canteen-menu' ? 'It is probably a canteen or food menu: keep every dish with its price.'
    : kind === 'bus-update' ? 'It is probably a bus route or timetable: keep stops and times.' : '';
  const prompt = 'Transcribe all text visible in this image exactly as written, keeping line breaks, prices, quantities and times. '
    + `${hint} If the image has no readable text about food, menus, prices, schedules, events, sports or announcements `
    + '(for example a photo of people, a meme or a sticker), reply with the single word NONE. Do not add commentary.';
  const response = await retryFetch('https://api.cohere.com/v2/chat', {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.COHERE_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: env.VISION_MODEL, temperature: 0,
      messages: [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: `data:${mime};base64,${base64}` } }] }],
    }),
  });
  if (!response.ok) throw new Error(`Vision service error ${response.status}`);
  const text = ((await response.json()).message.content ?? []).filter((p) => p.type === 'text').map((p) => p.text).join('').trim();
  return text.toUpperCase().replace(/[. ]+$/g, '') === 'NONE' ? '' : text;
}

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function deliveryUrl(env, id, kind) {
  return env.CLOUDINARY_CLOUD_NAME
    ? `https://res.cloudinary.com/${env.CLOUDINARY_CLOUD_NAME}/${kind === 'image' ? 'image' : 'raw'}/upload/${id}` : null;
}

export function slugify(value) {
  return value.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

export function detectLanguage(text) {
  const fr = new Set('le la les des du et de pour une un est sont dans au aux que qui vous nous'.split(' '));
  const en = new Set('the and of for to is are in that with you we your will on'.split(' '));
  const words = (text.toLowerCase().match(/[\p{L}]+/gu) ?? []).slice(0, 400);
  const f = words.filter((w) => fr.has(w)).length;
  const e = words.filter((w) => en.has(w)).length;
  return f > e * 1.2 ? 'fr' : 'en';
}

// Paragraph chunking for short posts: pieces of about 380 tokens (1500 characters), each prefixed with the title.
export function chunkPost(title, body, maxChars = 1500) {
  const blocks = body.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const pieces = [];
  let current = '';
  for (const block of blocks) {
    const parts = block.length > maxChars ? block.match(new RegExp(`[\\s\\S]{1,${maxChars}}`, 'g')) : [block];
    for (const part of parts) {
      if (current && (current.length + part.length) > maxChars) {
        pieces.push(current);
        current = '';
      }
      current = current ? `${current}\n\n${part}` : part;
    }
  }
  if (current) pieces.push(current);
  return pieces.map((p) => ({ heading: '', content: `${title}\n\n${p}` }));
}
