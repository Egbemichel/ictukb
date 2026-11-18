// Baileys authentication state kept in the knowledge base database (through the Worker's admin API)
// instead of local files, so the listener survives restarts and redeployments on hosts without a disk.
import { BufferJSON, initAuthCreds, proto } from 'baileys';

export async function useRemoteAuthState(api, { prefix = 'wa:', flushMs = 400, log = console } = {}) {
  const cache = new Map(); // key -> parsed value | null
  const pending = new Map(); // key -> serialized value | null
  let timer = null;
  let chain = Promise.resolve();

  const name = (type, id) => `${prefix}${type}-${id}`;

  async function load(keys) {
    const missing = [...new Set(keys.filter((k) => !cache.has(k)))];
    for (let i = 0; i < missing.length; i += 200) {
      const part = missing.slice(i, i + 200);
      const values = await api.stateGet(part);
      for (const k of part) cache.set(k, values[k] != null ? JSON.parse(values[k], BufferJSON.reviver) : null);
    }
  }

  function put(key, value) {
    cache.set(key, value);
    pending.set(key, value == null ? null : JSON.stringify(value, BufferJSON.replacer));
    if (!timer) {
      timer = setTimeout(() => {
        timer = null;
        flush().catch((error) => log.warn?.(`session save failed, will retry: ${error.message}`));
      }, flushMs);
    }
  }

  function flush() {
    if (timer) { clearTimeout(timer); timer = null; }
    const batch = [...pending.entries()];
    pending.clear();
    chain = chain.then(async () => {
      for (let i = 0; i < batch.length; i += 200) {
        const part = batch.slice(i, i + 200);
        try {
          await api.stateSet(Object.fromEntries(part));
        } catch (error) {
          for (const [k, v] of part) if (!pending.has(k)) pending.set(k, v); // keep for the next attempt
          if (!timer) timer = setTimeout(() => { timer = null; flush().catch(() => {}); }, 5000);
          throw error;
        }
      }
    });
    return chain;
  }

  await load([`${prefix}creds`]);
  const creds = cache.get(`${prefix}creds`) ?? initAuthCreds();

  return {
    state: {
      creds,
      keys: {
        get: async (type, ids) => {
          const keys = ids.map((id) => name(type, id));
          await load(keys);
          const out = {};
          ids.forEach((id, i) => {
            let value = cache.get(keys[i]);
            if (type === 'app-state-sync-key' && value) value = proto.Message.AppStateSyncKeyData.fromObject(value);
            out[id] = value ?? undefined;
          });
          return out;
        },
        set: async (data) => {
          for (const type of Object.keys(data)) {
            for (const id of Object.keys(data[type])) put(name(type, id), data[type][id] ?? null);
          }
        },
      },
    },
    saveCreds: async () => {
      put(`${prefix}creds`, creds);
      await flush();
    },
    flush,
  };
}
