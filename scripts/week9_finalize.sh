#!/usr/bin/env bash
# Package week 9 (interpretation and the discussion draft) and push.
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
python scripts/week9_case_studies.py --selftest | tail -1

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
upsert Case_study_sites outputs/week9/case_sites.csv "Physical terrain facts (slope, roughness, craters) inside the 5 km window of every named site"
upsert Case_study_regions outputs/week9/case_regions.csv "Largest parameter-sensitive, robustly-safe and never-safe regions with their terrain medians"
upsert Case_study_figure outputs/week9/case_studies.png "Suitability map and P(safe) map with all sites annotated"

echo
echo "=== 3. git status ==="
git add -A
git status --short | head -30

echo
echo "=== 4. commit ==="
git commit -q \
  -m "week9: interpretation, failure cases and a paper-style discussion draft" \
  -m "- LS2 (a paper candidate site) is a reproducible terrain outlier: median slope 9.0 deg and median roughness 7.8 m inside its 5 km window, 2.5-3.9x the other three paper sites, with two mapped craters and the nearest 1.55 km away; the disagreement with the paper is therefore about criterion weighting (science value vs engineering safety), not about the model" \
  -m "- parameter-sensitive terrain is terrain near the thresholds: the largest sensitive region (7,439 km2) has median slope 6.2 deg / roughness 5.3 m, inside the perturbed boxes, while the largest robustly safe region (2,332 km2, containing our best site) sits at 1.6 deg / 1.6 m; the never-safe regions are crater interiors and rims (32 deg / 30 m)" \
  -m "- our best site (353.76E, 11.08N) is smoother than every paper site: median slope 1.5 deg (p95 3.8), median roughness 1.4 m" \
  -m "- docs/week9_discussion_CN.md: methods, results, discussion (failure cases, threshold geometry, external validation), six explicit limitations (3 of 5 factors, crater layer accuracy, H1 untested, threshold dominance, DEM vertical error, no analysis of threshold optimality), transferability, methodological recommendations and a draft English abstract" \
  || echo "(nothing to commit)"

echo
echo "=== 5. push ==="
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
unset http_proxy https_proxy
pushed=0
for attempt in 1 2 3; do
  if timeout 240 git push origin main > /tmp/lsm_w9_push.log 2>&1; then
    echo "  OK (direct, attempt $attempt)"; tail -2 /tmp/lsm_w9_push.log; pushed=1; break
  fi
  echo "  attempt $attempt failed:"; tail -2 /tmp/lsm_w9_push.log
  sleep 5
done
if [ "$pushed" = "0" ]; then
  GW=$(ip route | awk '/^default/{print $3}')
  export http_proxy="http://$GW:7897"
  export https_proxy="$http_proxy"
  echo "  retry via $http_proxy"
  timeout 300 git push origin main 2>&1 | tail -3 || true
fi
unset http_proxy https_proxy
echo "  ahead/behind: $(git rev-list --left-right --count main...origin/main)"

echo
echo "=== 6. one-way backup: repo -> Windows ==="
bash scripts/backup_to_windows.sh
echo
echo "[week9-finalize] DONE"
