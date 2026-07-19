#!/usr/bin/env bash
set -euo pipefail

branch="${1:-leaderboard/codec-frontier}"
remote="veigapunk"
fork_url="https://github.com/VeigaPunk/commavq.git"

test "$(git remote get-url origin)" = "https://github.com/commaai/commavq.git"
git config remote.origin.pushurl no_push://commaai-origin-forbidden

if git remote get-url "$remote" >/dev/null 2>&1; then
  test "$(git remote get-url "$remote")" = "$fork_url"
else
  git remote add "$remote" "$fork_url"
fi

if git show-ref --verify --quiet "refs/heads/$branch"; then
  git switch "$branch"
else
  git switch -c "$branch"
fi

printf 'origin push URL: %s\n' "$(git remote get-url --push origin)"
printf 'fork push command: git push -u %s HEAD:refs/heads/%s\n' "$remote" "$branch"
