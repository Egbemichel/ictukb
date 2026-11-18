import assert from 'node:assert/strict';
import { test } from 'node:test';
import { handleMessage, localParts } from '../src/handler.js';
import { matchRoute } from '../src/route.js';
import { makeTitle, redact } from '../src/sanitize.js';
import { State } from '../src/state.js';

const config = {
  timezone: 'Africa/Douala',
  onlyAdminMessages: true,
  officialEmailDomains: ['ictuniversity.edu.cm'],
  routes: [
    { label: 'ictu-community', match: ['The ICT-U community'], kind: 'announcement' },
    { label: 'food-order', match: ['Food Order'], kind: 'canteen-menu' },
    { label: 'sports', match: ['SPORTS COMMUNITY'], kind: 'student-life-post' },
  ],
};

const GROUPS = {
  'a@g.us': { subject: 'The ICT-U community', parentSubject: 'The ICT-U community', announce: true },
  'c@g.us': { subject: 'FALL 2023 ICTU', parentSubject: 'The ICT-U community', announce: true },
  'f@g.us': { subject: 'ICTU Food Order & Pick-Up', parentSubject: '', announce: true },
  'm@g.us': { subject: 'ICTU Food Order chat', parentSubject: '', announce: false, adminIds: new Set(['237600000001']) },
  'x@g.us': { subject: 'Random group', parentSubject: '', announce: true },
};

function makeCtx() {
  const calls = [];
  const api = {
    post: async (n) => { calls.push(['post', n]); return { id: `${n.kind}-${n.date}${n.key ? `-${n.key}` : ''}` }; },
    remove: async (id) => { calls.push(['remove', id]); return {}; },
    transcribe: async () => 'Rice and beans 500 FCFA\nCall 677123456',
  };
  const ctx = {
    config, api, calls,
    state: new State(null),
    log: { warn: () => {} },
    groupInfo: async (jid) => GROUPS[jid] ?? null,
    normalize: (m) => m,
    download: async () => Buffer.from('img'),
  };
  return ctx;
}

const TS = Date.UTC(2026, 10, 18, 11, 5) / 1000; // 12:05 in Douala (UTC+1)
const text = (jid, id, body) => ({ key: { remoteJid: jid, id }, messageTimestamp: TS, message: { conversation: body } });

test('local date and time use the configured timezone', () => {
  assert.deepEqual(localParts(Date.UTC(2026, 10, 18, 23, 30) / 1000, 'Africa/Douala'), { date: '2026-11-19', time: '00:30' });
});

test('routes use the community name and ignore unlisted groups', () => {
  assert.equal(matchRoute(config.routes, GROUPS['a@g.us']).label, 'ictu-community');
  assert.equal(matchRoute(config.routes, GROUPS['x@g.us']), null);
  assert.equal(matchRoute(config.routes, GROUPS['c@g.us']), null); // another admin-only group of the same community
});

test('redaction removes phone numbers, mentions and unofficial emails', () => {
  const out = redact('Call +237 677 12 34 56 or @237677123456 or a@gmail.com or admin@ictuniversity.edu.cm', ['ictuniversity.edu.cm']);
  assert.ok(!out.includes('677'));
  assert.ok(out.includes('[number removed]') && out.includes('@member') && out.includes('[email removed]'));
  assert.ok(out.includes('admin@ictuniversity.edu.cm'));
  assert.equal(makeTitle('*Classes resume Monday* 🚨\nmore'), 'Classes resume Monday');
});

test('an announcement is posted with a title, a unique key and the local date', async () => {
  const ctx = makeCtx();
  const result = await handleMessage(text('a@g.us', 'M1', '*Classes resume Monday*\nPlease note the new hours'), ctx);
  assert.equal(result.action, 'posted');
  const [, note] = ctx.calls[0];
  assert.equal(note.kind, 'announcement');
  assert.equal(note.title, 'Classes resume Monday');
  assert.equal(note.date, '2026-11-18');
  assert.equal(note.by, 'whatsapp-ictu-community');
  assert.match(note.key, /^classes-resume-monday-[0-9a-f]{6}$/);
  // delivering the same message again does nothing
  assert.equal((await handleMessage(text('a@g.us', 'M1', 'again'), ctx)).action, 'skip');
});

test('unlisted groups and messages from non-admin members are ignored', async () => {
  const ctx = makeCtx();
  assert.equal((await handleMessage(text('x@g.us', 'M2', 'hello there friends'), ctx)).action, 'skip');
  const member = text('m@g.us', 'M3', 'I want rice please for order');
  member.key.participant = '237699999999@s.whatsapp.net';
  assert.equal((await handleMessage(member, ctx)).action, 'skip');
  assert.equal(ctx.calls.length, 0);
  // the same group accepts a message from one of its admins (also when the sender id is a LID)
  const admin = text('m@g.us', 'M4', 'Menu today: rice and beans 500 FCFA');
  admin.key.participant = '123456789@lid';
  admin.key.participantAlt = '237600000001@s.whatsapp.net';
  assert.equal((await handleMessage(admin, ctx)).action, 'posted');
});

test('menu messages of one day are combined and a deleted message is removed', async () => {
  const ctx = makeCtx();
  await handleMessage(text('f@g.us', 'F1', 'Breakfast: tea 200 FCFA'), ctx);
  await handleMessage(text('f@g.us', 'F2', 'Lunch: rice 500 FCFA'), ctx);
  const last = ctx.calls.at(-1)[1];
  assert.equal(last.kind, 'canteen-menu');
  assert.match(last.text, /Breakfast: tea 200 FCFA/);
  assert.match(last.text, /Lunch: rice 500 FCFA/);
  assert.match(last.text, /Posted at 12:05/);

  const revoke = { key: { remoteJid: 'f@g.us', id: 'R1' }, messageTimestamp: TS, message: { protocolMessage: { type: 0, key: { id: 'F1' } } } };
  assert.equal((await handleMessage(revoke, ctx)).action, 'removed');
  const after = ctx.calls.at(-1)[1];
  assert.ok(!after.text.includes('Breakfast') && after.text.includes('Lunch'));

  const revokeLast = { ...revoke, message: { protocolMessage: { type: 0, key: { id: 'F2' } } } };
  await handleMessage(revokeLast, ctx);
  assert.deepEqual(ctx.calls.at(-1), ['remove', 'canteen-menu-2026-11-18']);
});

test('an edited announcement replaces the old post', async () => {
  const ctx = makeCtx();
  await handleMessage(text('a@g.us', 'E1', 'Exam hall changed to Hall B'), ctx);
  const edit = {
    key: { remoteJid: 'a@g.us', id: 'E2' }, messageTimestamp: TS,
    message: { protocolMessage: { type: 14, key: { id: 'E1' }, editedMessage: { conversation: 'Exam hall changed to Hall C' } } },
  };
  assert.equal((await handleMessage(edit, ctx)).action, 'posted');
  assert.equal(ctx.calls[1][0], 'remove');
  assert.match(ctx.calls[2][1].text, /Hall C/);
});

test('a menu photo is read, redacted and labelled as machine-read', async () => {
  const ctx = makeCtx();
  const msg = { key: { remoteJid: 'f@g.us', id: 'P1' }, messageTimestamp: TS, message: { imageMessage: { mimetype: 'image/jpeg', caption: '' } } };
  assert.equal((await handleMessage(msg, ctx)).action, 'posted');
  const note = ctx.calls[0][1];
  assert.match(note.text, /Rice and beans 500 FCFA/);
  assert.ok(!note.text.includes('677123456'));
  assert.match(note.text, /Read automatically from a photo/);
});
