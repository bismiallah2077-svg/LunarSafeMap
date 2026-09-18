#!/usr/bin/env bash
# Download a SLDEM2015 tile with resume and integrity check.
# Usage: scripts/download_sldem.sh <tile_id> [out_dir]
# Example:
#   scripts/download_sldem.sh SLDEM2015_512_00N_30N_315_360_FLOAT.IMG data/raw/sldem2015
#
# Source: SLDEM2015 (Barker et al., 2016), LOLA-derived DEM,
#         512 px/degree, float (km). Mirror: MIT lunar data node.

set -euo pipefail

TILE="${1:?usage: download_sldem.sh <tile_id> [out_dir]}"
OUT_DIR="${2:-data/raw/sldem2015}"
BASE_URL="http://imbrium.mit.edu/DATA/SLDEM2015/TILES/FLOAT_IMG"
mkdir -p "$OUT_DIR"

IMG="$OUT_DIR/$TILE"
LBL="$OUT_DIR/${TILE%.IMG}.LBL"
LOG="$OUT_DIR/download_${TILE%.IMG}.log"

# Expected full size for SLDEM2015 512 ppd tiles: 15360 x 23040 x 4 bytes
EXPECTED_BYTES=$((15360 * 23040 * 4))

echo "[$(date -Is)] downloading $TILE" | tee -a "$LOG"
curl -sS -C - --retry 10 --retry-delay 5 \
  -o "$IMG" "$BASE_URL/$TILE" \
  >>"$LOG" 2>&1

ACTUAL_BYTES=$(stat -c %s "$IMG")
echo "[$(date -Is)] size=$ACTUAL_BYTES expected=$EXPECTED_BYTES" | tee -a "$LOG"

if [ "$ACTUAL_BYTES" -ne "$EXPECTED_BYTES" ]; then
  echo "[$(date -Is)] ERROR: incomplete download" | tee -a "$LOG"
  exit 1
fi

if [ ! -f "$LBL" ]; then
  echo "[$(date -Is)] fetching label" | tee -a "$LOG"
  curl -sS --retry 5 --retry-delay 3 -o "$LBL" "$BASE_URL/${TILE%.IMG}.LBL" >>"$LOG" 2>&1
fi

echo "[$(date -Is)] DONE $TILE" | tee -a "$LOG"
