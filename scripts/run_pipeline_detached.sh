#!/usr/bin/env bash
cd /home/zwx/projects/LunarSafeMap || exit 1
mkdir -p docs logs
echo "=== week23 pipeline start $(date) ==="
bash scripts/run_week2_3.sh > logs/week23_run.log 2>&1
echo "=== week23 pipeline end $(date) ==="
