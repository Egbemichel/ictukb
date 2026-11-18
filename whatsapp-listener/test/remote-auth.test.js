import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Buffer } from 'node:buffer';
import { useRemoteAuthState } from '../src/remote-auth.js';
import { State } from '../src/state.js';

function fakeApi() {
  const store = new Map();
  const calls = { get: 0, set: 0 };
  return {
    store, calls,
    stateGet: async (keys) => { calls.get += 1; return Object.fromEntries(keys.filter((k) => store.has(k)).map((k) => [k, store.get(k)])); },
    stateSet: async (entries) => {
      calls.set += 1;
      for (const [k, v] of Object.entries(entries)) { if (v === null) store.delete(k); else store.set(k, v); }
    },
  };
}

test('a new session is created and saved, then restored by a second process', async () => {
  const api = fakeApi();
  const first = await useRemoteAuthState(api, { flushMs: 10 });
  assert.ok(first.state.creds.noiseKey, 'fresh credentials are generated');
  await first.state.keys.set({ 'pre-key': { 1: { private: Buffer.from('abc'), public: Buffer.from('def') } } });
  await first.saveCreds();
  assert.ok(api.store.has('wa:creds'));
  assert.ok(api.store.has('wa:pre-key-1'));

  const second = await useRemoteAuthState(api, { flushMs: 10 });
  assert.deepEqual(second.state.creds.noiseKey.private, first.state.creds.noiseKey.private);
  const keys = await second.state.keys.get('pre-key', ['1', '2']);
  assert.equal(Buffer.from(keys['1'].private).toString(), 'abc');
  assert.equal(keys['2'], undefined);
});

test('removed keys are deleted remotely and writes are batched', async () => {
  const api = fakeApi();
  const s = await useRemoteAuthState(api, { flushMs: 10 });
  await s.state.keys.set({ session: { a: { v: 1 }, b: { v: 2 }, c: { v: 3 } } });
  await s.flush();
  assert.equal(api.calls.set, 1); // three keys, one request
  await s.state.keys.set({ session: { a: null } });
  await s.flush();
  assert.equal(api.store.has('wa:session-a'), false);
  assert.equal(api.store.has('wa:session-b'), true);
});

test('listener state is restored from the remote store', async () => {
  const api = fakeApi();
  const one = await new State(null, { api, key: 'wa:listener-state' }).load();
  one.data.posts.M1 = { kind: 'announcement', docId: 'x', date: '2026-11-18' };
  await one.flush();
  const two = await new State(null, { api, key: 'wa:listener-state' }).load();
  assert.equal(two.data.posts.M1.docId, 'x');
});
