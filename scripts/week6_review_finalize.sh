#!/usr/bin/env bash
# Package the week-6 *manual review* round into the repository and push.
#
# This round turns two reported metrics into reality-referenced ones:
#   precision 0.451 -> 0.726   (40 random false positives, half are craters
#                               the Robbins catalogue is missing)
#   recall    0.533 -> 0.717   (40 random misses, 45 % are not identifiable
#                               at 59 m/px anyway)
# and then tests the hypothesis the review produced (lower the size filter).
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
echo "=== 2. upsert derived products (same id -> refreshed hash) ==="
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
upsert Crater_review_FP outputs/week6/review_false_positives.csv "40 randomly sampled spurious detections with the manual verdict (TP/FP) and a note"
upsert Crater_review_misses outputs/week6/review_misses.csv "40 randomly sampled misses judged for detectability at 59 m/px"
upsert Crater_review_misses_all outputs/week6/review_misses_all.csv "All 250 false negatives (reference list)"
upsert Crater_review_summary outputs/week6/review_summary.txt "Corrected precision (0.726) and detectable recall (0.717) with Wilson intervals"
upsert Crater_review_map_fp outputs/week6/review_fp_map.png "Quick-look map of the reviewed false positives"
upsert Crater_review_map_miss outputs/week6/review_miss_map.png "Quick-look map of the reviewed misses"
upsert Crater_size_sweep_05 outputs/week6/catalog_metrics_md0.5.csv "Detection metrics with the size filter lowered to 0.5 km"
upsert Crater_size_sweep_03 outputs/week6/catalog_metrics_md0.3.csv "Detection metrics with the size filter lowered to 0.3 km"
upsert Crater_sample_tiles outputs/week6/sample_tiles.png "Teaching figure: input DEM / label / prediction for three contrasting tiles"

echo
echo "=== 3. git status ==="
git add -A
git status --short | head -40

echo
echo "=== 4. commit ==="
git commit -q \
  -m "week6 review: manual sampling corrects precision and recall, and predicts a post-processing gain" \
  -m "- 40 uniform-random false positives reviewed: 50 % are real craters the Robbins catalogue is missing (cross-checked: 19 of the 20 sit on craters absent from the catalogue, 1 is a duplicate) -> precision 0.451 to 0.726 (0.644-0.807)" \
  -m "- the correction is concentrated in the 1-2 km bin (P 0.467 -> 0.804) and is essentially zero for 2-5 km (0.354 -> 0.419), so the '1-2 km is the bottleneck' story was partly a property of the reference catalogue" \
  -m "- 55 % of the genuine false positives are illumination/shadow artefacts, which is the first evidence for the H3 illumination-domain-shift hypothesis" \
  -m "- 40 uniform-random misses reviewed for detectability at 59 m/px: 45 % are not identifiable at all -> detectable recall 0.717 (0.655-0.788) instead of 0.533" \
  -m "- the review predicted that about 50 of the 250 misses are recoverable by relaxing the 1 km size filter; measured 44 (R 0.533 -> 0.615) at a precision cost of 0.451 -> 0.334" \
  -m "- new/changed: week6_review_false_positives.py (--random/--misses/--summarise, Wilson intervals, GBK-tolerant reading, refuses to overwrite filled verdicts), week6_show_sample.py, week6_mask_to_catalog.py (--min-det-km/--match-frac)" \
  -m "- docs: week6_crater_detection.md sections 7.3-7.5; README and the 1-6 week review updated" \
  || echo "(nothing to commit)"

echo
echo "=== 5. push ==="
export GIT_ASKPASS=$HOME/.git-askpass-lunarsafe.sh
unset http_proxy https_proxy
if timeout 180 git push origin main > /tmp/lsm_w6r_push.log 2>&1; then
  echo "  OK (direct)"; tail -2 /tmp/lsm_w6r_push.log
else
  echo "  direct push failed:"; tail -2 /tmp/lsm_w6r_push.log
  GW=$(ip route | awk '/^default/{print $3}')
  export http_proxy="http://$GW:7897"
  export https_proxy="$http_proxy"
  echo "  retry via $http_proxy"
  if timeout 300 git push origin main > /tmp/lsm_w6r_push2.log 2>&1; then
    echo "  OK (proxy)"; tail -2 /tmp/lsm_w6r_push2.log
  else
    echo "  proxy push failed:"; tail -4 /tmp/lsm_w6r_push2.log
  fi
fi
unset http_proxy https_proxy
echo "  ahead/behind: $(git rev-list --left-right --count main...origin/main)"
echo
echo "[week6-review-finalize] DONE"
