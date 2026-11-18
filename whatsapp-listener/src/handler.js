import { createHash } from 'node:crypto';
import { matchRoute } from './route.js';
import { clip, makeTitle, redact } from './sanitize.js';

const REVOKE = new Set([0, 'REVOKE']);
const EDIT = new Set([14, 'MESSAGE_EDIT']);
const IMAGE_NOTE = '(Read automatically from a photo; check the photo for exact details.)';

export function localParts(tsSeconds, tz) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date(tsSeconds * 1000));
  const get = (type) => parts.find((p) => p.type === type).value;
  const hour = get('hour') === '24' ? '00' : get('hour');
  return { date: `${get('year')}-${get('month')}-${get('day')}`, time: `${hour}:${get('minute')}` };
}

export function extractText(content) {
  return (
    content?.conversation
    ?? content?.extendedTextMessage?.text
    ?? content?.imageMessage?.caption
    ?? content?.videoMessage?.caption
    ?? content?.documentMessage?.caption
    ?? ''
  );
}

function ids(value) {
  return [value].flat().filter(Boolean).map((v) => String(v).split(':')[0].split('@')[0]);
}

export function isAdminSender(msg, info) {
  const sender = [...ids(msg.key?.participant), ...ids(msg.key?.participantAlt)];
  return sender.some((id) => info.adminIds?.has(id));
}

const shortHash = (id) => createHash('sha1').update(String(id)).digest('hex').slice(0, 6);

// Process one WhatsApp message. All side effects go through ctx so the logic can be tested.
export async function handleMessage(msg, ctx) {
  const { config, state, api, log } = ctx;
  const jid = msg.key?.remoteJid;
  if (!jid || !jid.endsWith('@g.us') || msg.key.fromMe || !msg.message) return { action: 'skip', reason: 'not a group message' };

  const info = await ctx.groupInfo(jid);
  if (!info) return { action: 'skip', reason: 'group unknown' };
  const route = matchRoute(config.routes, info);
  if (!route) return { action: 'skip', reason: 'group not listed' };
  // In an admin-only group every message is from an admin; elsewhere only admins' messages are used.
  if (config.onlyAdminMessages && !info.announce && !isAdminSender(msg, info)) {
    return { action: 'skip', reason: 'sender is not a group admin' };
  }

  const content = ctx.normalize(msg.message);
  const ts = Number(msg.messageTimestamp ?? Math.floor(Date.now() / 1000));
  const when = localParts(ts, config.timezone);
  const by = `whatsapp-${route.label}`;
  state.prune(when.date);

  const proto = content.protocolMessage;
  if (proto) {
    if (REVOKE.has(proto.type)) return finish(ctx, await remove(proto.key?.id, route, ctx));
    if (EDIT.has(proto.type)) {
      const edited = ctx.normalize(proto.editedMessage ?? {});
      const text = prepare(extractText(edited), config);
      const original = proto.key?.id;
      if (!state.data.posts[original] || text.length < 5) return { action: 'skip', reason: 'edit of unknown message' };
      return finish(ctx, await publish(route, original, text, state.data.posts[original].date ?? when.date, when, by, ctx));
    }
    return { action: 'skip', reason: 'protocol message' };
  }

  const id = msg.key.id;
  if (state.data.posts[id]) return { action: 'skip', reason: 'already processed' };

  let text = prepare(extractText(content), config);
  if (content.imageMessage) {
    try {
      const buffer = await ctx.download(msg);
      const read = prepare(await api.transcribe(buffer, content.imageMessage.mimetype ?? 'image/jpeg', route.kind), config);
      if (read) text = [text, read, IMAGE_NOTE].filter(Boolean).join('\n\n');
    } catch (error) {
      log.warn?.(`image could not be read: ${error.message}`);
    }
  }
  if (text.length < 5) return { action: 'skip', reason: 'no usable text' };
  return finish(ctx, await publish(route, id, text, when.date, when, by, ctx));
}

function prepare(raw, config) {
  return clip(redact(raw ?? '', config.officialEmailDomains));
}

async function finish(ctx, result) {
  ctx.state.save();
  return result;
}

async function publish(route, id, text, postDate, when, by, ctx) {
  const { api, state } = ctx;
  if (route.kind === 'canteen-menu') {
    const day = (state.data.menus[postDate] ??= []);
    const entry = day.find((e) => e.id === id);
    if (entry) entry.text = text;
    else day.push({ id, time: when.time, text });
    state.data.posts[id] = { kind: route.kind, date: postDate };
    await syncMenu(postDate, by, ctx);
    return { action: 'posted', kind: route.kind, date: postDate };
  }
  const previous = state.data.posts[id];
  if (previous?.docId) await api.remove(previous.docId).catch(() => {});
  const title = makeTitle(text, route.kind === 'announcement' ? 'Announcement' : 'Update');
  const key = `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 30)}-${shortHash(id)}`;
  const res = await api.post({ kind: route.kind, text, by, title, key, date: postDate });
  state.data.posts[id] = { kind: route.kind, docId: res.id, date: postDate };
  return { action: 'posted', kind: route.kind, docId: res.id };
}

async function syncMenu(date, by, ctx) {
  const { api, state } = ctx;
  const day = state.data.menus[date] ?? [];
  if (!day.length) {
    await api.remove(`canteen-menu-${date}`).catch(() => {});
    delete state.data.menus[date];
    return;
  }
  const combined = day.map((e) => `Posted at ${e.time}:\n${e.text}`).join('\n\n');
  await api.post({ kind: 'canteen-menu', text: clip(combined), by, date });
}

async function remove(id, route, ctx) {
  const { api, state } = ctx;
  const post = state.data.posts[id];
  if (!post) return { action: 'skip', reason: 'deleted message was not posted' };
  delete state.data.posts[id];
  if (post.kind === 'canteen-menu') {
    state.data.menus[post.date] = (state.data.menus[post.date] ?? []).filter((e) => e.id !== id);
    await syncMenu(post.date, `whatsapp-${route.label}`, ctx);
  } else if (post.docId) {
    await api.remove(post.docId).catch(() => {});
  }
  return { action: 'removed', kind: post.kind };
}
