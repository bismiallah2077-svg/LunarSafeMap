#!/usr/bin/env bash
# Package week-6 results (crater detection) into the repository and push.
#
# Note on what gets committed: .gitignore already excludes *.pt, *.tif and
# data/raw|interim, so the 5 MB model checkpoint and the big rasters stay local.
# What goes in is the code, the tests, the docs and the small derived products
# (CSV / GeoJSON / PNG) - plus size+sha256 records in
# data/metadata/derived_products.csv so the untracked files are still auditable.
set -e
M=/mnt/c/Users/zwx/Documents/Codex/2026-08-14/w
R=$HOME/projects/LunarSafeMap
cd "$R"

echo "=== 1. copy scripts / tests / docs / README ==="
cp -f $M/scripts/*.py $M/scripts/*.sh scripts/
chmod +x scripts/*.py scripts/*.sh
cp -f $M/docs/*.md docs/
mkdir -p tests && cp -f $M/tests/*.py tests/
cp -f $M/README.md README.md
echo "  scripts: $(ls scripts | wc -l), docs: $(ls docs/*.md | wc -l), tests: $(ls tests/*.py | wc -l)"

echo
echo "=== 2. register week-6 derived products (append, with sha256) ==="
OUT=data/metadata/derived_products.csv
mkdir -p "$(dirname "$OUT")"
[ -f "$OUT" ] || echo "product_id,path,size_bytes,sha256,note" > "$OUT"
add () {
  local id="$1" path="$2" note="$3"
  if grep -q "^${id}," "$OUT" 2>/dev/null; then
    echo "  = $id (already listed)"
    return 0
  fi
  if [ -f "$path" ]; then
    printf "%s,%s,%s,%s,%s\n" "$id" "$path" "$(stat -c %s "$path")" \
      "$(sha256sum "$path" | cut -d" " -f1)" "$note" >> "$OUT"
    echo "  + $id"
  else
    echo "  ! missing $path (skipped)"
  fi
}
add Robbins2018_catalogue data/raw/robbins/lunar_crater_database_robbins_2018.zip "USGS Robbins 2018 crater database, 96,227,201 bytes, 1,296,796 craters"
add Crater_labels_RimaeBode data/interim/week6/crater_mask_sldem.tif "Crater discs rasterised on the study-area DEM grid, 5.50 percent coverage"
add Crater_tiles_week6 data/interim/week6/tiles.csv "120 tiles of 256 px with the crater count of each"
add UNet_crater_weights outputs/week6/unet_craters.pt "PyTorch U-Net, 1,286,417 params, 12 epochs on CPU"
add Crater_catalogue_RimaeBode outputs/week6/craters_detected.geojson "632 detected craters with lon/lat/diameter"
add Crater_detection_metrics outputs/week6/catalog_metrics.csv "Detection-level precision/recall/F1 per diameter bin"
add Crater_pixel_metrics outputs/week6/metrics.csv "Pixel-level IoU/P/R/F1 on validation and study area"
add Crater_ablation_features outputs/week6/ablation_features.csv "Input-feature ablation: DEM / +slope / +slope+shade"
add Crater_pred_mask outputs/week6/study_area_crater_pred.tif "Study-area prediction, 3073x2561 px, 7.24 percent coverage"
add Crater_review_FP outputs/week6/review_false_positives.csv "Spurious detections listed for manual review (verdict column blank)"
add Crater_review_misses outputs/week6/review_misses.csv "Known craters that were not detected"
add Crater_review_map outputs/week6/review_fp_map.png "Quick-look: study DEM + Robbins circles + spurious detections"
add Crater_labels_vs_pred outputs/week6/labels_vs_pred.png "Side-by-side of the Robbins labels and the prediction"

echo
echo "=== 3. git status ==="
git add -A
git status --short | head -40

echo
echo "=== 4. commit ==="
git commit -q \
  -m "week6: PyTorch U-Net crater detection with Robbins 2018 labels" \
  -m "- labels: Robbins 2018 catalogue (1,296,796 craters), 9,457 in the training box, 535 in the study area; rasterised discs, 256 px tiles" \
  -m "- model: PyTorch U-Net, 1,286,417 params, BCE+Dice, per-tile robust standardisation, CPU training (12 epochs, 11 min)" \
  -m "- geographic split: train south of 14N, validate north of 14N, Rimae Bode is the untouched test area" \
  -m "- pixel level: test IoU 0.298 / F1 0.460; detection level: F1 0.488, 8/8 craters >= 5 km with zero false positives" \
  -m "- feature ablation (same seed, same 400 tiles): DEM F1 0.460 -> +slope 0.462 -> +slope+shade 0.548; slope only trades recall for precision, hillshade lifts precision 0.368->0.628 and cuts spurious detections 347->81 (detection F1 0.488->0.542)" \
  -m "- output: craters_detected.geojson (632 features with lon/lat/diameter); 8 debugging lessons documented" \
  -m "- tests: test_week6_labels.py (12 checks), test_week6_channels.py (17 checks, catches the (C,H,W) rot90 regression)" \
  -m "- docs: week6_crater_detection.md, progress review extended to weeks 1-6" \
  || echo "(nothing to commit)"

echo
echo "=== 5. push ==="
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
unset http_proxy https_proxy
if timeout 180 git push origin main > /tmp/lsm_w6_push.log 2>&1; then
  echo "  OK (direct)"; tail -2 /tmp/lsm_w6_push.log
else
  echo "  direct push failed:"; tail -2 /tmp/lsm_w6_push.log
  GW=$(ip route | awk '/^default/{print $3}')
  export http_proxy="http://$GW:7897"
  export https_proxy="$http_proxy"
  echo "  retry via $http_proxy"
  if timeout 300 git push origin main > /tmp/lsm_w6_push2.log 2>&1; then
    echo "  OK (proxy)"; tail -2 /tmp/lsm_w6_push2.log
  else
    echo "  proxy push failed:"; tail -4 /tmp/lsm_w6_push2.log
  fi
fi
unset http_proxy https_proxy
echo "  ahead/behind: $(git rev-list --left-right --count main...origin/main)"
echo
echo "[week6-finalize] DONE"
