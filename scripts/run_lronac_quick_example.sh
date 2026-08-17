#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE_DIR="$REPO_ROOT/examples/lronac_quick/LRONAC_example"
OUT_DIR="$EXAMPLE_DIR/repro_run"

mkdir -p "$OUT_DIR"
cd "$EXAMPLE_DIR"

parallel_stereo \
  M181058717LE_crop.cub M181073012LE_crop.cub \
  M181058717LE.json M181073012LE.json \
  --alignment-method local_epipolar \
  --left-image-crop-win 2259 1196 900 973 \
  --right-image-crop-win 2432 1423 1173 1218 \
  --stereo-algorithm asp_mgm \
  --subpixel-mode 9 \
  "$OUT_DIR/run"

point2dem --auto-proj-center \
  --errorimage "$OUT_DIR/run-PC.tif" \
  --orthoimage "$OUT_DIR/run-L.tif"

chmod +x scripts/run_lronac_quick_example.sh

