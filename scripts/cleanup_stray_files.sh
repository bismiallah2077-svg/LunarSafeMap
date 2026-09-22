#!/usr/bin/env bash
# Remove stray files that a mis-typed shell redirect left in the repository root.
set -e
cd $HOME/projects/LunarSafeMap

echo "=== repository root ==="
ls -la | head -25

echo
echo "=== suspicious files ==="
for f in "59.22" "=" "main"; do
  if [ -e "$f" ]; then
    echo "--- $f ($(stat -c %s "$f") bytes, tracked: $(git ls-files --error-unmatch "$f" 2>/dev/null && echo yes || echo no))"
    head -c 200 "$f"; echo
  fi
done

echo
echo "=== removing them ==="
git rm -q --ignore-unmatch "59.22" "=" "main" || true
rm -f "59.22" "=" "main"

echo "=== other untracked files in the root (not touched) ==="
git status --short | grep "^??" | head -20 || echo "  (none)"

git status --short | head -10
echo
if git diff --cached --quiet; then
  echo "nothing staged after cleanup"
else
  git commit -q -m "chore: remove stray files left by a mis-typed shell redirect"
  export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
  unset http_proxy https_proxy
  timeout 180 git push origin main 2>&1 | tail -2
fi
git rev-list --left-right --count main...origin/main