import fs from 'node:fs';
import path from 'node:path';

// Remembers which WhatsApp message produced which post, so that edits, deletions and re-deliveries
// are handled. It lives in a local file, or in the knowledge base database when a remote store is given
// (hosts without a disk). It holds only message ids, post ids and the menu lines of the current days.
export class State {
  constructor(file, remote = null) {
    this.file = file;
    this.remote = remote; // { api, key }
    this.data = { posts: {}, menus: {} };
    this.timer = null;
    if (file && fs.existsSync(file)) this.#adopt(fs.readFileSync(file, 'utf8'));
  }

  #adopt(text) {
    try {
      this.data = { posts: {}, menus: {}, ...JSON.parse(text) };
    } catch {
      // a corrupt store is replaced by an empty one
    }
  }

  async load() {
    if (!this.remote) return this;
    const values = await this.remote.api.stateGet([this.remote.key]);
    if (values[this.remote.key]) this.#adopt(values[this.remote.key]);
    return this;
  }

  save() {
    if (this.file) {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      fs.writeFileSync(this.file, JSON.stringify(this.data));
    }
    if (this.remote && !this.timer) {
      this.timer = setTimeout(() => {
        this.timer = null;
        this.flush().catch(() => {});
      }, 1000);
    }
  }

  async flush() {
    if (!this.remote) return;
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    await this.remote.api.stateSet({ [this.remote.key]: JSON.stringify(this.data) });
  }

  prune(todayIso, keepDays = 3) {
    const limit = new Date(`${todayIso}T00:00:00Z`).getTime() - keepDays * 86400000;
    for (const [id, post] of Object.entries(this.data.posts)) {
      if (new Date(`${post.date}T00:00:00Z`).getTime() < limit) delete this.data.posts[id];
    }
    for (const date of Object.keys(this.data.menus)) {
      if (new Date(`${date}T00:00:00Z`).getTime() < limit) delete this.data.menus[date];
    }
  }
}
