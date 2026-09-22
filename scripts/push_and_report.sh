#!/usr/bin/env bash
# Show the pending commit and push it (direct first, then via the Clash proxy).
cd $HOME/projects/LunarSafeMap
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh

echo "=== recent commits ==="
git log --oneline -4

echo
echo "=== files in the pending commit (HEAD) ==="
git show --stat --oneline HEAD | head -45

echo
echo "=== ahead / behind (local...remote) ==="
git rev-list --left-right --count main...origin/main

echo
echo "=== push attempt 1: direct ==="
unset http_proxy https_proxy
if git push origin main > /tmp/lsm_push1.log 2>&1; then
  echo "  OK (direct)"; tail -2 /tmp/lsm_push1.log
else
  echo "  direct push failed:"; tail -2 /tmp/lsm_push1.log
  echo
  echo "=== push attempt 2: via Clash proxy ==="
  GW=$(ip route | awk '/^default/{print $3}')
  export http_proxy="http://$GW:7897"
  export https_proxy="$http_proxy"
  echo "  using $http_proxy"
  if git push origin main > /tmp/lsm_push2.log 2>&1; then
    echo "  OK (proxy)"; tail -2 /tmp/lsm_push2.log
  else
    echo "  proxy push failed:"; tail -4 /tmp/lsm_push2.log
  fi
fi

echo
echo "=== final state (local...remote) ==="
unset http_proxy https_proxy
git fetch origin > /dev/null 2>&1 || echo "  (fetch failed - network)"
git rev-list --left-right --count main...origin/main
echo "[done]"