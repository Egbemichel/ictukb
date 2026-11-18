// Privacy filters applied to every message before it leaves the listener.

const PHONE = /(?<![\w/])\+?\d[\d ().-]{7,}\d(?![\w/])/g;
const MENTION = /@\d{6,}/g;
const EMAIL = /[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)/g;

export const MAX_CHARS = 5800;

export function redact(text, officialDomains = []) {
  const allowed = new Set(officialDomains.map((d) => d.toLowerCase()));
  return text
    .replace(EMAIL, (m, domain) => (allowed.has(domain.toLowerCase()) ? m : '[email removed]'))
    .replace(MENTION, '@member')
    .replace(PHONE, '[number removed]')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export function clip(text) {
  return text.length > MAX_CHARS ? `${text.slice(0, MAX_CHARS)}...` : text;
}

// A short title for a post: the first line with markdown and emoji marks removed.
export function makeTitle(text, fallback = 'Announcement') {
  const first = text.split('\n').map((l) => l.trim()).find((l) => /[\p{L}\p{N}]/u.test(l)) ?? '';
  const cleaned = first
    .replace(/[*_~`#>]/g, '')
    .replace(/[^\p{L}\p{N}\p{P}\p{Zs}]/gu, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) return fallback;
  return cleaned.length > 70 ? `${cleaned.slice(0, 67)}...` : cleaned;
}

export function normalizeName(value) {
  return (value ?? '')
    .normalize('NFKD')
    .replace(/[^\p{L}\p{N} ]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}
