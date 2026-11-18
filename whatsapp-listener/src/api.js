// Client for the knowledge base admin API.

async function call(base, token, method, route, body, attempts = 4) {
  let lastError;
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(`${base}${route}`, {
        method,
        headers: { 'X-Admin-Token': token, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (response.status >= 500 || response.status === 429) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}: ${JSON.stringify(payload).slice(0, 200)}`);
        error.permanent = true;
        throw error;
      }
      return payload;
    } catch (error) {
      if (error.permanent) throw error;
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 1000 * 2 ** i));
    }
  }
  throw lastError;
}

export function makeApi(base, token) {
  return {
    post: (note) => call(base, token, 'POST', '/v1/admin/notes', note),
    remove: (docId) => call(base, token, 'DELETE', `/v1/admin/notes/${encodeURIComponent(docId)}`),
    transcribe: (buffer, mime, kind) =>
      call(base, token, 'POST', '/v1/admin/transcribe', {
        image_base64: buffer.toString('base64'),
        mime,
        kind,
      }).then((r) => r.text ?? ''),
  };
}
