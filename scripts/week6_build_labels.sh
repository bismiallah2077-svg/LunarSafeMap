#!/usr/bin/env bash
# Week 6.1: build the crater detection label set.
# Uses the browser-downloaded Robbins zip if present, otherwise falls back to
# the (slower) in-script download.  Runs the unit test before touching data.
set -e
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate lunarsafe
cd $HOME/projects/LunarSafeMap
M=/mnt/c/Users/zwx/Documents/Codex/2026-08-14/w

echo "=== 0. sync files ==="
cp "$M/scripts/week6_build_crater_labels.py" scripts/
mkdir -p tests && cp "$M/tests/test_week6_labels.py" tests/

echo "=== 1. self test ==="
python tests/test_week6_labels.py | tail -3

echo "=== 2. stage the browser-downloaded catalogue ==="
SRC=/mnt/c/Users/zwx/Downloads/lunar_crater_database_robbins_2018.zip
DST=data/raw/robbins/lunar_crater_database_robbins_2018.zip
if [ -f "$SRC" ] && [ "$(stat -c %s "$SRC")" -eq 96227201 ]; then
  mkdir -p "$(dirname "$DST")"
  cp -f "$SRC" "$DST"
  echo "  copied ($(stat -c %s "$DST") bytes) - skipping the slow download"
else
  echo "  browser zip missing or wrong size; the script will download it instead"
  GW=$(ip route | awk '/^default/{print $3}')
  export http_proxy="http://$GW:7897"
  export https_proxy="$http_proxy"
fi

echo "=== 3. build labels ==="
python scripts/week6_build_crater_labels.py