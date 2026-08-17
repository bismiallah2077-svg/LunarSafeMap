#!/usr/bin/env bash
# Preprocess one LROC NAC EDR product through ISIS:
#   lronac2isis -> spiceinit -> lronaccal -> cam2map
set -eo pipefail
export PDAL_DRIVER_PATH="${PDAL_DRIVER_PATH:-}"
source /home/zwx/miniconda3/etc/profile.d/conda.sh
conda activate asp
export ISISDATA="$CONDA_PREFIX/data"

EDR="$1"                 # path to MXXXXXXXXLE.IMG
WORK="$2"                # output work directory
RES="${3:-4}"            # map resolution in m/px (default 4)
CLON="${4:-$(echo 15.3)}"

mkdir -p "$WORK"
IMG_BASE="$(basename "$EDR" .IMG)"

echo "[isis] lronac2isis $IMG_BASE"
lronac2isis from="$EDR" to="$WORK/${IMG_BASE}.cub"

echo "[isis] spiceinit $IMG_BASE"
spiceinit from="$WORK/${IMG_BASE}.cub" > "$WORK/${IMG_BASE}_spiceinit.log" 2>&1 || \
  spiceinit from="$WORK/${IMG_BASE}.cub" web=yes

echo "[isis] lronaccal $IMG_BASE"
lronaccal from="$WORK/${IMG_BASE}.cub" to="$WORK/${IMG_BASE}_cal.cub" > "$WORK/${IMG_BASE}_cal.log" 2>&1

echo "[isis] camrange $IMG_BASE"
camrange from="$WORK/${IMG_BASE}_cal.cub" to="$WORK/${IMG_BASE}_range.pvl" > "$WORK/${IMG_BASE}_camrange.log" 2>&1

echo "[isis] maptemplate $IMG_BASE"
RANGE_FILE=$(ls "$WORK"/${IMG_BASE}_range.pvl* 2>/dev/null | head -1)
MINLAT=$(sed -n 's/.*MinimumLatitude *= *\([-0-9.]*\).*/\1/p' "$RANGE_FILE" | head -1)
MAXLAT=$(sed -n 's/.*MaximumLatitude *= *\([-0-9.]*\).*/\1/p' "$RANGE_FILE" | head -1)
EAST_BLOCK=$(awk '/Group = PositiveEast180/,/End_Group/' "$RANGE_FILE")
MINLON=$(echo "$EAST_BLOCK" | sed -n 's/.*MinimumLongitude *= *\([-0-9.]*\).*/\1/p' | head -1)
MAXLON=$(echo "$EAST_BLOCK" | sed -n 's/.*MaximumLongitude *= *\([-0-9.]*\).*/\1/p' | head -1)
echo "range: lat $MINLAT..$MAXLAT lon $MINLON..$MAXLON"
maptemplate map="$WORK/${IMG_BASE}.map" targopt=user targetname=moon proj=simplecyl \
  clon="$CLON" resopt=mpp resolution="$RES" rngopt=user \
  minlat="$MINLAT" maxlat="$MAXLAT" minlon="$MINLON" maxlon="$MAXLON"

echo "[isis] cam2map $IMG_BASE"
MAP_FILE=$(ls "$WORK"/${IMG_BASE}.map* 2>/dev/null | head -1)
if [ -n "$MAP_FILE" ]; then
  cam2map from="$WORK/${IMG_BASE}_cal.cub" to="$WORK/${IMG_BASE}_map.cub" map="$MAP_FILE" > "$WORK/${IMG_BASE}_cam2map.log" 2>&1 || \
    cam2map from="$WORK/${IMG_BASE}_cal.cub" to="$WORK/${IMG_BASE}_map.cub" defaultrange=yes
else
  cam2map from="$WORK/${IMG_BASE}_cal.cub" to="$WORK/${IMG_BASE}_map.cub" defaultrange=yes
fi

echo "[isis] gdal convert $IMG_BASE"
gdal_translate -q -of GTiff "$WORK/${IMG_BASE}_map.cub" "$WORK/${IMG_BASE}_map.tif"
echo "[isis] DONE $IMG_BASE -> $WORK/${IMG_BASE}_map.tif"
