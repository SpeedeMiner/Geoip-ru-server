#!/usr/bin/env bash
set -euo pipefail

if [[ "${GITHUB_REF:-}" != refs/heads/main || "${GITHUB_EVENT_NAME:-}" != workflow_dispatch ]]; then
  echo "::error::CDN repair is available only by manual dispatch on main"
  exit 1
fi
[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]
scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export GIT_TERMINAL_PROMPT=0
origin="https://github.com/$GITHUB_REPOSITORY.git"
snapshot="$(git ls-remote --exit-code --refs "$origin" refs/heads/release | cut -f1)"
[[ "$snapshot" =~ ^[0-9a-f]{40}$ ]]

# Only a CDN ref and its caches may be written by this workflow.
SNAPSHOT_SHA="$snapshot" V41_REQUIRE_CDN_READBACK=1 bash "$scripts/deliver_v41_cdn.sh"
