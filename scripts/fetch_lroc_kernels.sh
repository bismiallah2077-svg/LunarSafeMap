#!/usr/bin/env bash
# 补齐 LROC 2022 年 5 月的 SPICE 内核（本地内核集不含该时期）
set -e
GW=$(ip route | awk '/^default/{print $3}')
export http_proxy="http://$GW:7897"
export https_proxy="$http_proxy"
echo "[kernels] proxy=$http_proxy"

LRO=~/miniconda3/envs/asp/data/lro/kernels
NAIF_SPK=https://naif.jpl.nasa.gov/pub/naif/pds/data/lro-l-spice-6-v1.0/lrosp_1000/data/spk
NAIF_CK=https://naif.jpl.nasa.gov/pub/naif/LRO/kernels/ck

mkdir -p "$LRO/spk" "$LRO/ck"

echo "[kernels] SPK ..."
curl -L --retry 3 -o "$LRO/spk/fdf29r_2022121_2022152_v01.bsp" \
     "$NAIF_SPK/lrorg_2022074_2022166_v01.bsp"

echo "[kernels] CK ..."
curl -L --retry 3 -o "$LRO/ck/lrolc_2022120_2022152_v01.bc" \
     "$NAIF_CK/lrolc_2022120_2022152_v01.bc"

echo "[kernels] done:"
ls -la "$LRO/spk/fdf29r_2022121_2022152_v01.bsp" "$LRO/ck/lrolc_2022120_2022152_v01.bc"