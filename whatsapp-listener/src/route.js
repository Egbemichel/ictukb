import { normalizeName } from './sanitize.js';

// Find the configured route for a group by the group's own name. (The "Announcements" group of a
// WhatsApp community carries the community's name.) A route may set matchParent to also use the
// name of the community the group belongs to.
export function matchRoute(routes, info) {
  return (
    routes.find((r) => {
      const haystack = normalizeName(r.matchParent ? `${info.parentSubject ?? ''} ${info.subject ?? ''}` : info.subject);
      return r.match.some((m) => haystack.includes(normalizeName(m)));
    }) ?? null
  );
}
