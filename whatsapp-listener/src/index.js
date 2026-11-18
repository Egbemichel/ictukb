// WhatsApp listener: watches the official admin-only groups listed in groups.json and posts their
// menu, bus and announcement messages to the knowledge base API.
//
//   npm run link     first run: shows a pairing code to enter in WhatsApp > Linked devices
//   npm start        normal run
//   npm run groups   lists the groups the linked number belongs to and how each is routed
//   npm run logout   unlinks this device from WhatsApp
//
// The linked-device session is kept in the knowledge base database (AUTH_STORE=remote, the default),
// so the process can run on a host without a disk. AUTH_STORE=file keeps it in ./auth instead.

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import makeWASocket, {
  Browsers, DisconnectReason, downloadMediaMessage, fetchLatestBaileysVersion, normalizeMessageContent,
  useMultiFileAuthState,
} from 'baileys';
import pino from 'pino';
import { makeApi } from './api.js';
import { handleMessage } from './handler.js';
import { useRemoteAuthState } from './remote-auth.js';
import { matchRoute } from './route.js';
import { State } from './state.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const config = JSON.parse(fs.readFileSync(path.join(root, 'groups.json'), 'utf8'));
const env = process.env;
const AUTH_DIR = env.AUTH_DIR ?? path.join(root, 'auth');
const STATE_FILE = env.STATE_FILE ?? path.join(root, 'state', 'state.json');
const KB_API_URL = (env.KB_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const ADMIN_TOKEN = env.ADMIN_TOKEN ?? '';
const PAIRING_PHONE = (env.PAIRING_PHONE ?? '').replace(/\D/g, '');
const mode = process.argv.includes('--groups') ? 'groups' : process.argv.includes('--link') ? 'link'
  : process.argv.includes('--logout') ? 'logout' : 'run';
const AUTH_STORE = env.AUTH_STORE === 'file' ? 'file' : 'remote';
const PORT = Number(env.PORT ?? 8080);

const log = pino({ level: env.LOG_LEVEL ?? 'info' });
const quiet = pino({ level: 'silent' });
const stamp = () => new Date().toISOString();
const out = {
  info: (m) => console.log(`${stamp()} ${m}`),
  warn: (m) => console.warn(`${stamp()} WARN ${m}`),
};

if ((mode === 'run' || AUTH_STORE === 'remote') && !ADMIN_TOKEN) {
  console.error('ADMIN_TOKEN is not set');
  process.exit(1);
}

const api = makeApi(KB_API_URL, ADMIN_TOKEN);
const state = AUTH_STORE === 'remote'
  ? await new State(null, { api, key: 'wa:listener-state' }).load()
  : new State(STATE_FILE);
const health = { connected: false, since: null, started: new Date().toISOString() };
const infoCache = new Map();
let retry = 0;

async function start() {
  const { state: auth, saveCreds, flush: flushAuth } = AUTH_STORE === 'remote'
    ? await useRemoteAuthState(api, { log: out })
    : await useMultiFileAuthState(AUTH_DIR);
  const flushAll = async () => { await flushAuth?.(); await state.flush(); };
  process.removeAllListeners('SIGTERM');
  process.on('SIGTERM', () => flushAll().finally(() => process.exit(0)));
  process.on('SIGINT', () => flushAll().finally(() => process.exit(0)));
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    version, auth, logger: quiet, browser: Browsers.ubuntu('Chrome'), printQRInTerminal: false,
    markOnlineOnConnect: false, syncFullHistory: false, getMessage: async () => undefined,
  });
  let pairingRequested = false;

  async function groupInfo(jid) {
    const hit = infoCache.get(jid);
    if (hit && hit.until > Date.now()) return hit.value;
    let value = null;
    try {
      const meta = await sock.groupMetadata(jid);
      let parentSubject = '';
      if (meta.linkedParent) {
        try { parentSubject = (await sock.groupMetadata(meta.linkedParent)).subject ?? ''; } catch { /* parent not visible */ }
      }
      const adminIds = new Set();
      for (const part of meta.participants ?? []) {
        if (!part.admin) continue;
        for (const id of [part.id, part.phoneNumber, part.lid]) {
          if (id) adminIds.add(String(id).split(':')[0].split('@')[0]);
        }
      }
      value = { id: jid, subject: meta.subject ?? '', parentSubject, announce: Boolean(meta.announce || meta.isCommunityAnnounce), adminIds };
    } catch (error) {
      out.warn(`group metadata unavailable for ${jid}: ${error.message}`);
    }
    infoCache.set(jid, { value, until: Date.now() + (value ? 10 * 60 * 1000 : 60 * 1000) });
    return value;
  }

  const ctx = {
    config, state, api, log: out, groupInfo,
    normalize: (m) => normalizeMessageContent(m) ?? {},
    download: (msg) => downloadMediaMessage(msg, 'buffer', {}, { logger: quiet, reuploadRequest: sock.updateMediaMessage }),
  };

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr && !sock.authState.creds.registered && !pairingRequested) {
      if (!PAIRING_PHONE) {
        out.warn('Not linked. Set PAIRING_PHONE (international format, digits only) and run: npm run link');
        process.exit(1);
      }
      pairingRequested = true;
      const code = await sock.requestPairingCode(PAIRING_PHONE);
      console.log(`\nPairing code: ${code}\nOn the phone: WhatsApp > Settings > Linked devices > Link a device > Link with phone number instead.\n`);
    }
    if (connection === 'open') {
      retry = 0;
      health.connected = true;
      health.since = new Date().toISOString();
      out.info('connected to WhatsApp');
      if (mode === 'logout') {
        await sock.logout();
        out.info('device unlinked');
        process.exit(0);
      }
      if (mode === 'link') {
        out.info('linked. Stop this process (Ctrl+C) and start the listener with: npm start');
      } else {
        await report(sock, groupInfo, mode === 'groups');
      }
    }
    if (connection === 'close') {
      health.connected = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      if (code === DisconnectReason.connectionReplaced) {
        out.warn('Another instance is using this WhatsApp session; stopping this one.');
        await flushAll().catch(() => {});
        process.exit(1);
      }
      if (code === DisconnectReason.loggedOut) {
        out.warn('Logged out of WhatsApp. Re-link with: npm run link');
        process.exit(1);
      }
      if (mode === 'groups') process.exit(0);
      retry += 1;
      const delay = code === DisconnectReason.restartRequired ? 500 : Math.min(30000, 1000 * 2 ** retry);
      out.warn(`connection closed (${code}); reconnecting in ${delay} ms`);
      setTimeout(start, delay);
    }
  });

  if (mode === 'run') {
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (type !== 'notify') return;
      for (const msg of messages) {
        try {
          const result = await handleMessage(msg, ctx);
          if (result.action !== 'skip') out.info(`${result.action} ${result.kind ?? ''} ${result.docId ?? result.date ?? ''}`.trim());
        } catch (error) {
          out.warn(`message ${msg.key?.id} failed: ${error.message}`);
        }
      }
    });
  }
}

// Lists every group of the linked number, how it is routed, and warns about routes without a group.
async function report(sock, groupInfo, exitAfter) {
  const groups = Object.values(await sock.groupFetchAllParticipating());
  const used = new Set();
  const rows = [];
  for (const g of groups) {
    const info = await groupInfo(g.id);
    if (!info) continue;
    const route = matchRoute(config.routes, info);
    if (route) used.add(route.label);
    rows.push({ group: info.subject, community: info.parentSubject, adminOnlyGroup: info.announce, admins: info.adminIds.size, route: route?.label ?? '-', kind: route?.kind ?? '-' });
  }
  console.table(rows);
  for (const r of config.routes) if (!used.has(r.label)) out.warn(`route "${r.label}" matches no group of this number`);
  for (const r of rows) if (r.route !== '-' && !r.adminOnlyGroup) out.warn(`"${r.group}": members can post here, so only messages from its ${r.admins} admins are used`);
  if (exitAfter) process.exit(0);
}

if (mode === 'run') {
  http.createServer((req, res) => {
    const ok = req.url === '/healthz' ? true : health.connected;
    res.writeHead(req.url === '/healthz' || ok ? 200 : 503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: health.connected ? 'connected' : 'connecting', ...health }));
  }).listen(PORT, () => out.info(`health endpoint on port ${PORT}`));
}

process.on('unhandledRejection', (error) => out.warn(`unhandled: ${error?.message ?? error}`));
log.debug('starting');
start();
