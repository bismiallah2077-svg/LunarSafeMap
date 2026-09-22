#!/usr/bin/env bash
# Week 5.4: first-pass landing risk map (slope + roughness), with a threshold sweep.
set -e
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe
cd $HOME/projects/LunarSafeMap
M=/mnt/c/Users/zwx/Documents/Codex/2026-08-14/w
cp "$M/scripts/week5_risk_map.py" scripts/
mkdir -p tests && cp "$M/tests/test_week5_risk.py" tests/ 2>/dev/null || true
echo "=== self test ==="
python tests/test_week5_risk.py | tail -3
echo
echo "=== risk map ==="
python scripts/week5_risk_map.py