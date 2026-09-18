#!/usr/bin/env python3
"""Build a tile index over the Rimae Bode study area.

Tiles are square blocks of the study-area DEM (default 512 x 512 px, about
30 km on a side at 59 m/px). The index lists each tile's pixel window, its
geographic bounds, elevation statistics and mean slope, so later stages
(terrain metrics, crater detection, suitability) can iterate tiles instead of
loading the whole scene.

Usage:
  python scripts/build_tiles.py --tile-size 512 \
      --dem data/interim/week4/sldem_rimae_bode.tif \
      --out outputs/week4/tile_index.csv
"""
import argparse
import csv
import math
from pathlib import Path

import numpy as np
from osgeo import gdal

REPO = Path(__file__).resolve().parents[1]
MOON_M_PER_DEG = 30320.0  # 2*pi*1737400 m / 360


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="data/interim/week4/sldem_rimae_bode.tif")
    ap.add_argument("--out", default="outputs/week4/tile_index.csv")
    ap.add_argument("--tile-size", type=int, default=512)
    ap.add_argument("--min-valid-frac", type=float, default=0.5,
                    help="skip tiles with less valid data than this")
    args = ap.parse_args()

    dem_path = REPO / args.dem
    ds = gdal.Open(str(dem_path))
    if ds is None:
        raise FileNotFoundError(dem_path)
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype("float32")
    nodata = band.GetNoDataValue()
    gt = ds.GetGeoTransform()
    nrows, ncols = arr.shape
    ds = None

    valid = np.isfinite(arr)
    if nodata is not None:
        valid &= arr != nodata

    px_m = abs(gt[1]) * MOON_M_PER_DEG
    tile = args.tile_size
    ntx = math.ceil(ncols / tile)
    nty = math.ceil(nrows / tile)

    rows_out = []
    for ty in range(nty):
        for tx in range(ntx):
            c0, r0 = tx * tile, ty * tile
            c1, r1 = min(c0 + tile, ncols), min(r0 + tile, nrows)
            sub = arr[r0:r1, c0:c1]
            m = valid[r0:r1, c0:c1]
            if sub.shape[0] < 3 or sub.shape[1] < 3:
                continue  # edge sliver: too small for a gradient
            frac = float(m.mean()) if m.size else 0.0
            if frac < args.min_valid_frac:
                continue

            vals = sub[m]
            if vals.size < 2:
                continue

            # slope from the local gradient (metres per pixel)
            gy, gx = np.gradient(np.where(m, sub, np.nan))
            slope = np.degrees(np.arctan(np.hypot(gx, gy) / px_m))
            slope_valid = slope[np.isfinite(slope)]

            lon_min = gt[0] + c0 * gt[1]
            lon_max = gt[0] + c1 * gt[1]
            lat_max = gt[3] + r0 * gt[5]
            lat_min = gt[3] + r1 * gt[5]

            rows_out.append({
                "tile_id": f"T{ty:03d}_{tx:03d}",
                "row0": r0, "col0": c0,
                "rows": r1 - r0, "cols": c1 - c0,
                "lon_min": round(lon_min, 6), "lon_max": round(lon_max, 6),
                "lat_min": round(lat_min, 6), "lat_max": round(lat_max, 6),
                "mean_elev_m": round(float(vals.mean()), 2),
                "std_elev_m": round(float(vals.std()), 2),
                "min_elev_m": round(float(vals.min()), 2),
                "max_elev_m": round(float(vals.max()), 2),
                "mean_slope_deg": round(float(slope_valid.mean()), 3),
                "p95_slope_deg": round(float(np.percentile(slope_valid, 95)), 3),
                "valid_frac": round(frac, 4),
            })

    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    print(f"DEM: {dem_path.name}  {nrows} x {ncols} px, {px_m:.1f} m/px")
    print(f"tile size: {tile} px ({tile * px_m / 1000:.1f} km)")
    print(f"tiles written: {len(rows_out)} -> {out}")
    steep = sorted(rows_out, key=lambda r: -r["p95_slope_deg"])[:3]
    print("steepest tiles (p95 slope):")
    for r in steep:
        print(f"  {r['tile_id']}  p95={r['p95_slope_deg']:.1f} deg  "
              f"mean={r['mean_slope_deg']:.1f}  elev={r['mean_elev_m']:.0f} m")


if __name__ == "__main__":
    main()