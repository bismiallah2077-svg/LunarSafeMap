#!/usr/bin/env python3
"""Compare an ASP DEM against a reference DEM (SLDEM2015 or NAC DTM).

Outputs:
  - difference raster (ASP - reference) in the ASP DEM grid
  - summary table (mean, RMSE, percentiles) as CSV
  - error vs slope / shadow / texture binned table + figures
"""
import argparse
import csv
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

def read_band(path: Path, band=1):
    ds = gdal.Open(str(path), gdal.GA_ReadOnly)
    arr = ds.GetRasterBand(band).ReadAsArray().astype(np.float64)
    nodata = ds.GetRasterBand(band).GetNoDataValue()
    gt = ds.GetGeoTransform()
    proj = ds.GetProjection()
    cols, rows = ds.RasterXSize, ds.RasterYSize
    ds = None
    return arr, nodata, gt, proj, cols, rows

def warp_to(reference: Path, target: Path, out: Path):
    """Reproject/resample reference raster onto the ASP DEM grid."""
    ds = gdal.Open(str(reference))
    tgt = gdal.Open(str(target))
    gt = tgt.GetGeoTransform()
    xres = abs(gt[1])
    yres = abs(gt[5])
    bounds = (gt[0], gt[3] + tgt.RasterYSize * gt[5], gt[0] + tgt.RasterXSize * gt[1], gt[3])
    dst = gdal.Warp(str(out), ds,
                    format="GTiff",
                    dstSRS=tgt.GetProjection(),
                    outputBounds=bounds,
                    xRes=xres,
                    yRes=yres,
                    resampleAlg="bilinear",
                    srcNodata=0.0, dstNodata=-9999)
    dst.FlushCache()
    dst = None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True, help="ASP DEM (GeoTIFF)")
    ap.add_argument("--ref", required=True, help="reference DEM (SLDEM .IMG/.tif)")
    ap.add_argument("--drg", help="orthoimage for shadow/texture")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    dem, dem_nodata, dem_gt, dem_proj, _, _ = read_band(Path(args.dem))
    warped = out / "ref_on_dem_grid.tif"
    warp_to(Path(args.ref), Path(args.dem), warped)
    ref, ref_nodata, _, _, _, _ = read_band(warped)

    mask = (dem != dem_nodata) & (np.isfinite(dem)) & (ref != -9999) & (np.isfinite(ref))
    diff = dem - ref
    valid = diff[mask]

    stats = {
        "n": int(valid.size),
        "mean": float(valid.mean()),
        "std": float(valid.std()),
        "rmse": float(np.sqrt((valid ** 2).mean())),
        "mae": float(np.abs(valid).mean()),
        "median": float(np.median(valid)),
        "p1": float(np.percentile(valid, 1)),
        "p99": float(np.percentile(valid, 99)),
    }
    with open(out / "dem_error_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats))
        w.writeheader()
        w.writerow(stats)

    # write difference raster
    dout = out / "dem_difference.tif"
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(dout), dem.shape[1], dem.shape[0], 1, gdal.GDT_Float32)
    ds.SetGeoTransform(dem_gt)
    ds.SetProjection(dem_proj)
    b = ds.GetRasterBand(1)
    b.WriteArray(diff)
    b.SetNoDataValue(dem_nodata)
    ds = None

    # covariate analysis: slope, shadow (brightness), texture (local std)
    def slope_map(dem_arr):
        gy, gx = np.gradient(dem_arr)
        return np.degrees(np.arctan(np.hypot(gx, gy)))

    slope = slope_map(dem)
    covariate_analyses = {}
    covariate_analyses["slope_deg"] = slope
    if args.drg:
        br, br_nodata, _, _, _, _ = read_band(Path(args.drg))
        br = np.where(br == br_nodata, np.nan, br)
        covariate_analyses["brightness"] = br
        from scipy import ndimage  # lazy import
        covariate_analyses["texture_std"] = ndimage.generic_filter(
            br, np.nanstd, size=5, mode="constant", cval=np.nan)

    bin_rows = []
    for name, cov in covariate_analyses.items():
        cmask = mask & np.isfinite(cov)
        if cmask.sum() == 0:
            continue
        edges = np.nanpercentile(cov[cmask], [0, 20, 40, 60, 80, 100])
        edges[-1] += 1e-9
        for i in range(len(edges) - 1):
            sel = cmask & (cov >= edges[i]) & (cov < edges[i + 1])
            if sel.sum() == 0:
                continue
            d = diff[sel]
            bin_rows.append({
                "covariate": name,
                "bin": f"{edges[i]:.2f}-{edges[i+1]:.2f}",
                "n": int(sel.sum()),
                "mean": float(d.mean()),
                "rmse": float(np.sqrt((d ** 2).mean())),
            })
    with open(out / "error_vs_covariates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["covariate", "bin", "n", "mean", "rmse"])
        w.writeheader()
        w.writerows(bin_rows)

    print(stats)
    print(f"covariate bins: {len(bin_rows)}")

if __name__ == "__main__":
    main()
