#!/usr/bin/env bash
# Package week-5 results into the repository and push.
set -e
M=/mnt/c/Users/zwx/Documents/Codex/2026-08-14/w
R=$HOME/projects/LunarSafeMap
cd "$R"

echo "=== 1. copy files ==="
cp -f $M/scripts/*.py $M/scripts/*.sh scripts/
chmod +x scripts/*.py scripts/*.sh
cp -f $M/docs/*.md docs/
cp -f $M/README.md README.md
echo "  scripts: $(ls scripts | wc -l), docs: $(ls docs/*.md | wc -l)"

echo
echo "=== 2. git status ==="
git add -A
git status --short | head -30

echo
echo "=== 3. commit ==="
git commit -q -m "week5: slope threshold crossings, multi-scale terrain metrics, 1-5 week review" -m "- slope fields agree at matched resolution (median -0.05 deg, MAE 1.58 deg) but SLDEM misses 11.4/16.9/31.1 percent of the terrain steeper than 10/15/20 deg" -m "- multi-scale metrics at 20/60/200 m: the fraction steeper than 20 deg falls from 2.8 percent to 1.6 percent as the DEM coarsens" -m "- affine residual model improves RMSE by only 2.8 percent: no scale/rotation misregistration" -m "- docs: docs/progress_review_weeks1_5.md (plan vs actual, downloads, sites, tools, scripts, outputs, conclusions); manual updated with the SPICE kernel recipe and resume instructions" || echo "(nothing to commit)"

echo
echo "=== 4. push ==="
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
unset http_proxy https_proxy
if timeout 180 git push origin main 2>&1 | tail -3; then echo "  (push attempted)"; fi
git rev-list --left-right --count main...origin/main
echo
echo "[week5-finalize] DONE"