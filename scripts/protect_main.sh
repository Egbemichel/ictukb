#!/usr/bin/env bash
# Protect the main branch: pull requests only, one approval from a code owner, required checks green.
# Requires the GitHub CLI authenticated as a repository admin.
# Usage: scripts/protect_main.sh OWNER/REPO
set -euo pipefail

repo="${1:?usage: protect_main.sh OWNER/REPO}"

gh api --method PUT "repos/${repo}/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["checks"] },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "require_code_owner_reviews": true,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

for label in stale-content wrong-answer missing-info; do
  gh label create "$label" --repo "$repo" --force >/dev/null
done
echo "main is protected on ${repo}"
