#!/usr/bin/env bash
# Week 5.3: spatial structure of the NAC-minus-SLDEM residual.
set -e
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe
cd $HOME/projects/LunarSafeMap
cp /mnt/c/Users/zwx/Documents/Codex/2026-08-14/w/scripts/week5_error_spatial.py scripts/
python scripts/week5_error_spatial.py