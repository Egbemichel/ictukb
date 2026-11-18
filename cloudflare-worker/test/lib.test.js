import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildTsQuery, chunkPost, detectLanguage, isStale, safeEqual, slugify } from '../src/lib.js';

test('keyword query drops stopwords and joins with OR', () => {
  assert.equal(buildTsQuery('How do I pay fees in installments?'), 'pay | fees | installments');
  assert.equal(buildTsQuery('is it'), 'zzzznomatchzzzz');
});

test('staleness follows the tier limits', () => {
  const old = new Date(Date.now() - 130 * 86400000).toISOString().slice(0, 10);
  assert.equal(isStale('semester', old), true);
  assert.equal(isStale('static', old), false);
  assert.equal(isStale('realtime', old, 365), false);
});

test('short posts are chunked with the title prefix', () => {
  const chunks = chunkPost('Canteen menu for 2026-11-18', 'Rice 500 FCFA\n\nBeans 300 FCFA');
  assert.equal(chunks.length, 1);
  assert.ok(chunks[0].content.startsWith('Canteen menu for 2026-11-18'));
  const long = chunkPost('Title', Array.from({ length: 40 }, (_, i) => `Paragraph ${i} ${'x'.repeat(100)}`).join('\n\n'));
  assert.ok(long.length > 2);
});

test('helpers', () => {
  assert.equal(slugify('Génie logiciel / Year 2'), 'genie-logiciel-year-2');
  assert.equal(detectLanguage('Les étudiants doivent payer les frais pour la rentrée'), 'fr');
  assert.equal(safeEqual('abc', 'abc'), true);
  assert.equal(safeEqual('abc', 'abd'), false);
});
