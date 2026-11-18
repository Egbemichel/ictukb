import fs from 'node:fs';
import path from 'node:path';

// Small JSON store that remembers which WhatsApp message produced which post, so that edits,
// deletions and re-deliveries are handled. It holds no message text of other kinds than the
// menu entries of the current days.
export class State {
  constructor(file) {
    this.file = file;
    this.data = { posts: {}, menus: {} };
    if (file && fs.existsSync(file)) {
      try {
        this.data = { posts: {}, menus: {}, ...JSON.parse(fs.readFileSync(file, 'utf8')) };
      } catch {
        // a corrupt file is replaced by an empty store
      }
    }
  }

  save() {
    if (!this.file) return;
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    fs.writeFileSync(this.file, JSON.stringify(this.data));
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
