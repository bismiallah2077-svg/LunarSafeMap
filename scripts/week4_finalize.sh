#!/usr/bin/env bash
# Package week-4 results into the repository and push to GitHub.
set -e
M=/mnt/c/Users/zwx/Documents/Codex/2026-08-14/w
R=$HOME/projects/LunarSafeMap
cd "$R"

echo "=== 1. copy scripts / configs / docs ==="
cp -f $M/scripts/*.py  scripts/
cp -f $M/scripts/*.sh  scripts/
chmod +x scripts/*.py scripts/*.sh
cp -f $M/configs/*.yaml $M/configs/*.csv configs/
cp -f $M/docs/*.md docs/
cp -f $M/README.md README.md
echo "  scripts: $(ls scripts | wc -l) files, docs: $(ls docs/*.md | wc -l) files"

echo
echo "=== 2. register derived products (with sha256) ==="
OUT=data/metadata/derived_products.csv
echo "product_id,path,size_bytes,sha256,note" > "$OUT"
add() {
  local id="$1" path="$2" note="$3"
  if [ -f "$path" ]; then
    printf "%s,%s,%s,%s,%s\n" "$id" "$path" "$(stat -c %s "$path")" "$(sha256sum "$path" | cut -d" " -f1)" "$note" >> "$OUT"
    echo "  + $id"
  else
    echo "  ! missing $path (skipped)"
  fi
}
add NAC_M1406988604LE_EDR data/raw/lroc_nac_rimae_bode/M1406988604LE.IMG "LROC NAC EDR, orbit 57968, stereo partner"
add NAC_M1406995626LE_EDR data/raw/lroc_nac_rimae_bode/M1406995626LE.IMG "LROC NAC EDR, orbit 57969, primary"
add NAC_DEM_RimaeBode outputs/week4/nac_dem.tif "ASP DEM, 3.283 m/px, 2176x13866"
add NAC_ORTHO_RimaeBode outputs/week4/nac_ortho.tif "ASP orthoimage, same grid"
add NAC_IntersectionErr outputs/week4/nac_intersection_err.tif "ASP triangulation error (median 4.46 m)"
add NAC_vs_SLDEM_stats outputs/week4/nac_vs_sldem_stats.csv "DEM comparison statistics"
add NAC_vs_SLDEM_coreg outputs/week4/nac_vs_sldem_coregistration.csv "registration and slope dependence"

echo
echo "=== 3. git status ==="
git add -A
git status --short | head -30

echo
echo "=== 4. commit ==="
git commit -q -m "week4: Rimae Bode NAC stereo DEM and validation against SLDEM2015

- stereo pair M1406988604LE + M1406995626LE (2022-05-12, convergence 23.1 deg)
  located by scanning the LROC volume indexes, validated with stereo_check.py
- ISIS import/calibrate/project -> ASP parallel_stereo + point2dem
  (run_nac_pair_rimae_bode.sh, with --processes 4 to avoid OOM)
- hand-supplied SPICE kernels for 2022 LROC data documented in
  docs/lroc_spice_kernels.md (lrorg SPK, lrosc bus CK, lrolc camera CK)
- DEM 2176x13866 px at 3.283 m/px, intersection error median 4.46 m
- vs SLDEM2015: median offset -0.83 m, RMSE 35.3 m, but MAE 4 m below 5 deg
  slope and ~88 m above 25 deg; registration ruled out as the cause
- derived products registered in data/metadata/derived_products.csv
- week5_slope_safety_analysis.py staged for the start of week 5" || echo "(nothing to commit)"

echo
echo "=== 5. push ==="
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
unset http_proxy https_proxy
timeout 180 git push origin main 2>&1 | tail -3
git rev-list --left-right --count main...origin/main
echo
echo "[finalize] DONE"