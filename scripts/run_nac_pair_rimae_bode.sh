#!/usr/bin/env bash
# Rimae Bode NAC stereo pair -> DEM  (week 4/5)
#
# Pair (verified with scripts/stereo_check.py):
#   M1406988604LE  orbit 57968  slew  -6.14 deg  inc 48.7  emis 4.7   0.849 m/px
#   M1406995626LE  orbit 57969  slew +16.10 deg  inc 47.7  emis 18.6  0.885 m/px
#   convergence 23.1 deg, 2022-05-12, volume LROLRC_0051B
#
# Pipeline: ISIS import/calibrate -> project to a common map -> ASP stereo ->
#           compare against SLDEM2015.
set -eo pipefail

source /home/zwx/miniconda3/etc/profile.d/conda.sh
conda activate asp
export ISISDATA="$CONDA_PREFIX/data"

# --- networking: reach the Windows Clash proxy from NAT-mode WSL ---
if [ -z "${http_proxy:-}" ]; then
  GW=$(ip route | awk '/^default/{print $3}')
  if [ -n "$GW" ]; then
    export http_proxy="http://$GW:7897"
    export https_proxy="$http_proxy"
  fi
fi
echo "[pair] proxy = ${http_proxy:-none}"
if ! curl -s -m 8 -o /dev/null -w "" https://astrogeology.usgs.gov/ ; then
  echo "[pair] WARNING: no internet - spiceinit will need local kernels"
fi

REPO=/home/zwx/projects/LunarSafeMap
RAW="$REPO/data/raw/lroc_nac_rimae_bode"
WORK="$REPO/data/interim/nac_pair"
OUT="$REPO/outputs/week4"
mkdir -p "$WORK" "$OUT"

LEFT=M1406988604LE
RIGHT=M1406995626LE

# study window around the overlap centre (9.88N, 354.81E)
LAT0=9.80; LAT1=9.96
LON0=354.73; LON1=354.89
RES=1.0
CLON=354.81

for id in "$LEFT" "$RIGHT"; do
  echo "[pair] ==== $id ===="
  [ -f "$WORK/$id.cub" ] || lronac2isis from="$RAW/$id.IMG" to="$WORK/$id.cub"
  if [ ! -f "$WORK/$id.spice_ok" ]; then
    # the spacecraft bus attitude (lrosc, frame -85000) goes in CK=;
    # the temperature corrected LROC camera attitude (lrolc, frame -85600) is loaded as an
    # EXTRA kernel, so no comma separated list is needed
    spiceinit from="$WORK/$id.cub" \
      SPK="$ISISDATA/lro/kernels/spk/lrorg_2022074_2022166_v01.bsp" \
      CK="$ISISDATA/lro/kernels/ck/lrosc_2022131_2022141_v01.bc" \
      EXTRA="$ISISDATA/lro/kernels/ck/lrolc_2022120_2022152_v01.bc" \
      || spiceinit from="$WORK/$id.cub" web=yes
    touch "$WORK/$id.spice_ok"
  fi
  [ -f "$WORK/${id}_cal.cub" ] || lronaccal from="$WORK/$id.cub" to="$WORK/${id}_cal.cub"
  if [ ! -f "$WORK/$id.map" ]; then
    maptemplate map="$WORK/$id.map" targopt=user targetname=moon proj=simplecyl \
      clon=$CLON resopt=mpp resolution=$RES rngopt=user \
      minlat=$LAT0 maxlat=$LAT1 minlon=$LON0 maxlon=$LON1
  fi
  [ -f "$WORK/${id}_map.cub" ] || cam2map from="$WORK/${id}_cal.cub" \
      to="$WORK/${id}_map.cub" map="$WORK/$id.map"
  gdal_translate -q -of GTiff "$WORK/${id}_map.cub" "$OUT/${id}_projected.tif"
done

echo "[pair] ---- ASP stereo ----"
cd "$WORK"
if [ ! -f "$WORK/run-DEM.tif" ]; then
  # --processes limits concurrency: ASP defaults to one process per core with
  # extra threads, which can exhaust RAM on a laptop and hard-reset the machine.
  parallel_stereo "$WORK/${LEFT}_map.cub" "$WORK/${RIGHT}_map.cub" \
    --processes 4 \
    --alignment-method local_epipolar \
    --stereo-algorithm asp_mgm \
    --subpixel-mode 9 \
    "$WORK/run"
  point2dem --auto-proj-center --errorimage \
    --orthoimage "$WORK/run-L.tif" "$WORK/run-PC.tif"
fi
cp -f "$WORK/run-DEM.tif" "$OUT/nac_dem.tif" || true
cp -f "$WORK/run-DRG.tif" "$OUT/nac_ortho.tif" || true
cp -f "$WORK/run-IntersectionErr.tif" "$OUT/nac_intersection_err.tif" || true

echo "[pair] ---- DEM statistics ----"
conda activate lunarsafe
gdalinfo -stats "$WORK/run-DEM.tif" | grep -E "Minimum|Maximum|Mean|StdDev" || true
echo "[pair] DONE - outputs in $OUT"
