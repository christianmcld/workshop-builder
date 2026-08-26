#!/usr/bin/env bash
# Publish an HTML workshop deck to the USER'S OWN GitHub Pages.
# Requires: gh CLI authenticated as the user (gh auth login). Their account, their repo.
#
# Usage: ./publish_pages.sh <dir-with-index.html> <repo-name> [--private]
set -euo pipefail
DIR="${1:?dir with index.html}"; REPO="${2:?repo name}"; VIS="${3:---public}"
[ -f "$DIR/index.html" ] || { echo "no index.html in $DIR"; exit 1; }
OWNER=$(gh api user -q .login)
cd "$DIR"
[ -d .git ] || git init -q -b main
git add -A && git commit -q -m "workshop deck" --allow-empty
gh repo view "$OWNER/$REPO" >/dev/null 2>&1 || gh repo create "$REPO" ${VIS/--/--} --source . >/dev/null
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
git push -q -u origin main
gh api -X POST "repos/$OWNER/$REPO/pages" -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 || \
gh api -X PUT "repos/$OWNER/$REPO/pages" -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 || true
echo "Presentation: https://$OWNER.github.io/$REPO/  (Pages can take ~1 min on first publish)"
