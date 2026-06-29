#!/usr/bin/env bash
# Remove accidentally committed local config files from entire git history.
# WARNING: rewrites history — coordinate with teammates before pushing.
set -euo pipefail

FILES=${1:-"config.local.json *.local.json"}

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "Install git-filter-repo first: pip install git-filter-repo"
  exit 1
fi

echo "This will rewrite history to remove: $FILES"
read -r -p "Continue? [y/N] " ans
if [[ "${ans:-}" != "y" && "${ans:-}" != "Y" ]]; then
  echo "Aborted."
  exit 1
fi

for f in $FILES; do
  git filter-repo --path "$f" --invert-paths --force
done

echo "Done. Verify with: git log --all -- config.local.json"
echo "Then force-push only if your team agrees: git push --force-with-lease"
