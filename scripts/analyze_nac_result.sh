#!/usr/bin/env bash
# Look at the finished NAC DEM and compare it with SLDEM2015.
set -e
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe
cd $HOME/projects/LunarSafeMap

echo "=== DEM header ==="
gdalinfo -stats outputs/week4/nac_dem.tif | grep -E "Size is|Pixel Size|Minimum|Maximum|Mean|StdDev|NoData"

echo
echo "=== intersection error file health ==="
gdalinfo -stats outputs/week4/nac_intersection_err.tif 2>&1 | grep -E "Size is|Driver|ERROR|Minimum|Mean" || echo "(gdalinfo could not open it)"

echo
echo "=== comparison with SLDEM2015 (full res + resolution matched) ==="
cp /mnt/c/Users/zwx/Documents/Codex/2026-08-14/w/scripts/compare_nac_to_sldem.py scripts/
python scripts/compare_nac_to_sldem.py