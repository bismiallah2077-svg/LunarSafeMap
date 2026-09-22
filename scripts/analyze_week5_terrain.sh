#!/usr/bin/env bash
# Week 5.2: multi-scale terrain metrics on the NAC DEM and on SLDEM.
set -e
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe
cd $HOME/projects/LunarSafeMap
cp /mnt/c/Users/zwx/Documents/Codex/2026-08-14/w/scripts/week5_terrain_metrics.py scripts/
python scripts/week5_terrain_metrics.py