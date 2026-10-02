#!/usr/bin/env bash
# Package week 7 (suitability model + AHP + literature validation) and push.
#
# NOTE (2026-10-02): this script does NOT copy anything from the Windows
# workspace into the repository.  The repository is the single source of truth;
# the Windows folder only receives a one-way backup at the end.  The old
# finalizers copied C: -> repo, which once overwrote a fresh edit with a stale
# copy - that is exactly the failure mode this ordering removes.
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
for tag in equal entropy calib50_95 ahp; do
  upsert "Suitability_${tag}" "outputs/week7/suitability_${tag}.tif" \
    "Suitability S (0-1) for the ${tag} weights; SLDEM 59.2 m grid"
  upsert "Suitability_summary_${tag}" "outputs/week7/suitability_summary_${tag}.csv" \
    "Weights, thresholds, class fractions and candidate count for ${tag}"
  upsert "Candidate_sites_${tag}" "outputs/week7/candidate_sites_${tag}.geojson" \
    "Top non-overlapping 5 km candidate sites, ranked by mean S (${tag})"
  upsert "Literature_comparison_${tag}" "outputs/week7/literature_comparison_${tag}.csv" \
    "Suitability of the paper's LS1-LS4 at the same 5 km window definition (${tag})"
done
upsert Hazard_slope outputs/week7/hazard_slope.tif "Slope hazard layer, 0-1 ramp 5-15 deg"
upsert Hazard_roughness outputs/week7/hazard_roughness.tif "Roughness hazard layer, 0-1 ramp 1-5 m"
upsert Hazard_crater outputs/week7/hazard_crater.tif "Crater hazard layer: 1 inside a mapped crater, decays over a 1 km rim buffer"
upsert Suitability_map outputs/week7/suitability_map.png "Six-panel figure: hazard layers, S, classes, histogram"
upsert Config_AHP_matrix configs/ahp_matrix.csv "Author's pairwise judgement (2026-10-02): weights 0.550/0.210/0.240, CR 0.0157"
upsert Config_landing_sites configs/landing_sites.csv "Paper LS1-LS4 coordinates read from Fig. 5, plus landmarks"

echo
echo "=== 3. git status ==="
git add -A
git status --short | head -40

echo
echo "=== 4. commit ==="
git commit -q \
  -m "week7: suitability model, AHP weights and validation against the paper's landing sites" \
  -m "- model: S = w_slope*H_slope + w_rough*H_rough + w_crater*H_crater on the SLDEM 59.2 m grid, with piecewise-linear hazard ramps (slope 5-15 deg, roughness 1-5 m, crater 1 inside / 1 km rim buffer) and reuse of the week-5 terrain metrics" \
  -m "- candidate landing sites are 5 km sliding windows, not the largest contiguous safe region (the first attempt returned a 10,724 km2 'site', which is 39 percent of the study area)" \
  -m "- equal weights 58.4 percent safe; entropy weights 75.6; percentile-calibrated thresholds 78.4; author's AHP weights (0.550/0.210/0.240, CR 0.0157) 70.7" \
  -m "- ranking stability: changing the weights keeps 9 of the top 10 candidate sites, changing the thresholds keeps only 5 - threshold uncertainty matters more than weight uncertainty here" \
  -m "- validation against Yang et al. 2026 Fig. 5 (LS1-LS4): LS3 is the safest of the four under all four parameterisations (80.6-86.2 percentile, 0 percent danger pixels, class safe) and LS2 the most hazardous under all four (0.7-1.9 percentile) - an independent confirmation plus one robust disagreement to discuss" \
  -m "- our own best site, (353.76 E, 11.08 N), is identical under every parameterisation and lies 26-73 km from all four paper sites; the paper also weighs scientific value, which our model does not" \
  -m "- new tools: week7_ahp.py (interactive pairwise comparison, geometric-mean weights, consistency ratio, 11 self tests), week7_compare_literature.py (11 self tests incl. a brute-force cross-check of the ranking)" \
  -m "- repository workflow: docs/script_index.md + tests/test_script_index.py make the navigation auditable; scripts/backup_to_windows.sh mirrors the repo to the Windows workspace one-way (the repo is the single source of truth)" \
  || echo "(nothing to commit)"

echo
echo "=== 5. push ==="
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
unset http_proxy https_proxy
if timeout 180 git push origin main > /tmp/lsm_w7_push.log 2>&1; then
  echo "  OK (direct)"; tail -2 /tmp/lsm_w7_push.log
else
  echo "  direct push failed:"; tail -2 /tmp/lsm_w7_push.log
  GW=$(ip route | awk '/^default/{print $3}')
  export http_proxy="http://$GW:7897"
  export https_proxy="$http_proxy"
  echo "  retry via $http_proxy"
  if timeout 300 git push origin main > /tmp/lsm_w7_push2.log 2>&1; then
    echo "  OK (proxy)"; tail -2 /tmp/lsm_w7_push2.log
  else
    echo "  proxy push failed:"; tail -4 /tmp/lsm_w7_push2.log
  fi
fi
unset http_proxy https_proxy
echo "  ahead/behind: $(git rev-list --left-right --count main...origin/main)"

echo
echo "=== 6. one-way backup: repo -> Windows ==="
bash scripts/backup_to_windows.sh
echo
echo "[week7-finalize] DONE"
