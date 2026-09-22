#!/usr/bin/env bash
# Test whether the NAC DEM and SLDEM are horizontally registered.
set -e
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe
cd $HOME/projects/LunarSafeMap
cp /mnt/c/Users/zwx/Documents/Codex/2026-08-14/w/scripts/coregister_nac_sldem.py scripts/
python scripts/coregister_nac_sldem.py