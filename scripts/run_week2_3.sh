#!/usr/bin/env bash
# Week 2-3: planetary data + ASP finishing + first DEM error analysis.
# Crop-first workflow: calibrate -> crop overlap -> project crops -> ASP stereo -> LDEM comparison.
set -eo pipefail
export PDAL_DRIVER_PATH="${PDAL_DRIVER_PATH:-}"
source /home/zwx/miniconda3/etc/profile.d/conda.sh
conda activate asp
export ISISDATA="$CONDA_PREFIX/data"

REPO=/home/zwx/projects/LunarSafeMap
RAW="$REPO/data/raw/lroc_nac_edr"
WORK="$REPO/data/interim/week23"
OUT="$REPO/outputs/week23"
mkdir -p "$WORK" "$OUT"

LEFT=M181058717LE
RIGHT=M181073012LE
RES=4
CLON=15.31

process_image() {
  local id="$1"
  local win="$2"
  local cub="$WORK/${id}.cub"
  local cal="$WORK/${id}_cal.cub"
  local crop="$WORK/${id}_crop.cub"
  local map="$WORK/${id}.map"
  local proj="$WORK/${id}_crop_map.cub"

  echo "[w23] == $id =="
  if [ ! -f "$cub" ]; then
    echo "[w23] lronac2isis"
    lronac2isis from="$RAW/${id}.IMG" to="$cub"
  fi
  if [ ! -f "$WORK/${id}_spice_ok" ]; then
    echo "[w23] spiceinit"
    spiceinit from="$cub" > "$WORK/${id}_spiceinit.log" 2>&1 || spiceinit from="$cub" web=yes
    touch "$WORK/${id}_spice_ok"
  fi
  if [ ! -f "$cal" ]; then
    echo "[w23] lronaccal"
    lronaccal from="$cub" to="$cal" > "$WORK/${id}_cal.log" 2>&1
  fi
  if [ ! -f "$crop" ]; then
    echo "[w23] crop"
    crop from="$cal" to="$crop" $win
  fi
  if [ ! -f "$map" ]; then
    echo "[w23] camrange+maptemplate"
    camrange from="$cal" to="$WORK/${id}_range.pvl" > "$WORK/${id}_camrange.log" 2>&1
    local range_file minlat maxlat minlon maxlon east_block
    range_file=$(ls "$WORK"/${id}_range.pvl* 2>/dev/null | head -1)
    minlat=$(sed -n 's/.*MinimumLatitude *= *\([-0-9.]*\).*/\1/p' "$range_file" | head -1)
    maxlat=$(sed -n 's/.*MaximumLatitude *= *\([-0-9.]*\).*/\1/p' "$range_file" | head -1)
    east_block=$(awk '/Group = PositiveEast180/,/End_Group/' "$range_file")
    minlon=$(echo "$east_block" | sed -n 's/.*MinimumLongitude *= *\([-0-9.]*\).*/\1/p' | head -1)
    maxlon=$(echo "$east_block" | sed -n 's/.*MaximumLongitude *= *\([-0-9.]*\).*/\1/p' | head -1)
    maptemplate map="$map" targopt=user targetname=moon proj=simplecyl \
      clon="$CLON" resopt=mpp resolution="$RES" rngopt=user \
      minlat="$minlat" maxlat="$maxlat" minlon="$minlon" maxlon="$maxlon"
  fi
  if [ ! -f "$proj" ]; then
    echo "[w23] cam2map (crop)"
    cam2map from="$crop" to="$proj" map="$map" > "$WORK/${id}_cam2map.log" 2>&1
  fi
  gdal_translate -q -of GTiff "$proj" "$OUT/${id}_projected.tif"
}

process_image "$LEFT" "sample=2259 line=1196 nsamples=900 nlines=973"
process_image "$RIGHT" "sample=2432 line=1423 nsamples=1173 nlines=1218"

echo "[w23] ASP stereo"
cd "$WORK"
if [ ! -f "$WORK/run-DEM.tif" ]; then
  parallel_stereo "$WORK/${LEFT}_crop.cub" "$WORK/${RIGHT}_crop.cub" \
    --alignment-method local_epipolar \
    --stereo-algorithm asp_mgm \
    --subpixel-mode 9 \
    "$WORK/run"
  point2dem --auto-proj-center \
    --errorimage "$WORK/run-PC.tif" \
    --orthoimage "$WORK/run-L.tif"
fi
cp -f "$WORK/run-DEM.tif" "$OUT/dem_asp.tif"
cp -f "$WORK/run-DRG.tif" "$OUT/ortho_asp.tif"
cp -f "$WORK/run-IntersectionErr.tif" "$OUT/intersection_err.tif"

echo "[w23] LDEM reference analysis"
LDEM="$CONDA_PREFIX/data/base/dems/ldem_128ppd_Mar2011_clon180_radius_pad.cub"
if [ -f "$LDEM" ]; then
  gdal_translate -q -of GTiff "$LDEM" "$WORK/ldem_128.tif"
  conda activate lunarsafe
  python "$REPO/scripts/compare_dem.py" \
    --dem "$WORK/run-DEM.tif" \
    --ref "$WORK/ldem_128.tif" \
    --drg "$WORK/run-DRG.tif" \
    --out "$OUT"
fi
echo "[w23] DONE"
