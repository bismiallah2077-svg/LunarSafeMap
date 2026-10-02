#!/usr/bin/env bash
# Package week 8 (Monte Carlo uncertainty) and push.
#
# Same ordering as week7_finalize.sh: tests first, then register, commit, push,
# and only at the very end mirror the repository to the Windows backup folder.
set -e
R=$HOME/projects/LunarSafeMap
cd "$R"
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe

echo "=== 1. pre-flight checks ==="
python tests/test_script_index.py | tail -2
python scripts/week7_suitability.py --selftest | tail -1
python scripts/week7_ahp.py --selftest | tail -1
python scripts/week7_compare_literature.py --selftest | tail -1
python scripts/week8_montecarlo.py --selftest | tail -1

echo
echo "=== 2. upsert derived products ==="
OUT=data/metadata/derived_products.csv
mkdir -p "$(dirname "$OUT")"
[ -f "$OUT" ] || echo "product_id,path,size_bytes,sha256,note" > "$OUT"
upsert () {
  local id="$1" path="$2" note="$3"
  if [ -f "$path" ]; then
    grep -v "^${id}," "$OUT" > "$OUT.tmp" || true
    printf "%s,%s,%s,%s,%s\n" "$id" "$path" "$(stat -c %s "$path")" \
      "$(sha256sum "$path" | cut -d" " -f1)" "$note" >> "$OUT.tmp"
    mv "$OUT.tmp" "$OUT"
    echo "  + $id"
  else
    echo "  ! missing $path (skipped)"
  fi
}
for tag in k15 k60; do
  upsert "MC_sites_${tag}" "outputs/week8/mc_sites_${tag}.csv" \
    "Per-site rank percentile distribution over 200 Monte Carlo draws (${tag})"
  upsert "MC_draws_${tag}" "outputs/week8/mc_draws_${tag}.csv" \
    "Every Monte Carlo draw: weights, thresholds, buffer, catalogue, safe fraction"
  upsert "MC_prob_safe_${tag}" "outputs/week8/mc_prob_safe_${tag}.tif" \
    "Per-pixel probability of being classified safe over 200 draws (${tag})"
  upsert "MC_prob_danger_${tag}" "outputs/week8/mc_prob_danger_${tag}.tif" \
    "Per-pixel probability of being classified danger over 200 draws (${tag})"
  upsert "MC_summary_${tag}" "outputs/week8/mc_summary_${tag}.png" \
    "Four-panel Monte Carlo summary figure (${tag})"
done

echo
echo "=== 3. git status ==="
git add -A
git status --short | head -40

echo
echo "=== 4. commit ==="
git commit -q \
  -m "week8: Monte Carlo uncertainty of the landing-site ranking" \
  -m "- 200 draws per scenario perturbing weights (Dirichlet around the AHP vector), slope thresholds {3,5,8}/{10,15,20} deg, roughness {0.5,1,2}/{3,5,10} m, rim buffer {500,1000,2000} m and the crater catalogue (632 precision / 897 recall); DEM, terrain, grid and the 5 km window stay fixed" \
  -m "- speed: the rim distance transform is computed once per catalogue and rescaled per draw, so 200 draws take 3.3 minutes" \
  -m "- area is uncertain, ranking is not: the safe fraction spans 0.38-0.93 (5-95 percent, wide weights) and 0.44-0.91 at about +/-30 percent weights, yet the study-area top sites keep rank percentile >= 99 in every draw" \
  -m "- validation survives: the paper's LS3 stays the safest of its four sites (79-88 percentile in every draw) and LS2 the most hazardous (<= 4 percentile)" \
  -m "- thresholds dominate the uncertainty: group spread in the safe fraction is 0.177 (slope safe threshold), 0.161 (slope danger), 0.147 (roughness danger), 0.115 (rim buffer) versus 0.034 for the crater catalogue; among weights the roughness weight correlates most strongly (r = -0.44)" \
  -m "- spatial result: 26.1 percent of the study area is safe under every parameter combination, 35.2 percent is parameter-dependent (0.1 < P(safe) < 0.9) and 6.3 percent is never safe" \
  -m "- also: script_index.md gains the week-7/8 entries (the index test caught a missing week7_finalize.sh entry, which is exactly its job)" \
  || echo "(nothing to commit)"

echo
echo "=== 5. push ==="
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
unset http_proxy https_proxy
if timeout 240 git push origin main > /tmp/lsm_w8_push.log 2>&1; then
  echo "  OK (direct)"; tail -2 /tmp/lsm_w8_push.log
else
  echo "  direct push failed:"; tail -2 /tmp/lsm_w8_push.log
  GW=$(ip route | awk '/^default/{print $3}')
  export http_proxy="http://$GW:7897"
  export https_proxy="$http_proxy"
  echo "  retry via $http_proxy"
  if timeout 300 git push origin main > /tmp/lsm_w8_push2.log 2>&1; then
    echo "  OK (proxy)"; tail -2 /tmp/lsm_w8_push2.log
  else
    echo "  proxy push failed:"; tail -4 /tmp/lsm_w8_push2.log
  fi
fi
unset http_proxy https_proxy
echo "  ahead/behind: $(git rev-list --left-right --count main...origin/main)"

echo
echo "=== 6. one-way backup: repo -> Windows ==="
bash scripts/backup_to_windows.sh
echo
echo "[week8-finalize] DONE"
