#!/usr/bin/env bash
# Install the 2022 LROC SPICE kernels needed by spiceinit for M1406988604LE /
# M1406995626LE, then run the Rimae Bode stereo pipeline.  Safe to re-run.
set -e

SRC_LIST="/mnt/c/Users/zwx/Downloads /mnt/c/Users/zwx/Documents/Codex/2026-08-14/w/downloads/lroc_kernels"
LRO=$HOME/miniconda3/envs/asp/data/lro/kernels

find_kernel() {   # $1 = name, $2 = expected size
  for d in $SRC_LIST; do
    if [ -f "$d/$1" ] && [ "$(stat -c %s "$d/$1")" -eq "$2" ]; then echo "$d/$1"; return 0; fi
  done
  return 1
}

install_one() {   # $1 = name, $2 = size, $3 = dest subdir
  local src
  if src=$(find_kernel "$1" "$2"); then
    mkdir -p "$LRO/$3"
    cp -f "$src" "$LRO/$3/"
    echo "[install] $1  <- $src"
  else
    echo "[install] MISSING or incomplete: $1 (need $2 bytes) - download it in your browser"
    MISSING=1
  fi
}

MISSING=0
install_one lrorg_2022074_2022166_v01.bsp 7743488 spk
install_one lrosc_2022131_2022141_v01.bc 508795904 ck
install_one lrolc_2022120_2022152_v01.bc  15416320 ck
[ "$MISSING" -eq 0 ] || { echo; echo "[install] 还有文件没准备好，先别继续"; exit 1; }
rm -f "$LRO/spk/fdf29r_2022121_2022152_v01.bsp"

cd "$HOME/projects/LunarSafeMap"
cp -f /mnt/c/Users/zwx/Documents/Codex/2026-08-14/w/scripts/run_nac_pair_rimae_bode.sh scripts/
rm -f data/interim/nac_pair/*.spice_ok
echo "[install] running the pipeline ..."
bash scripts/run_nac_pair_rimae_bode.sh