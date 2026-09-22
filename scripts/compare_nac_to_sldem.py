#!/usr/bin/env python3
"""Compare the ASP NAC DEM (Rimae Bode pair) against SLDEM2015.

Two comparisons are produced:
  * full resolution  - NAC DEM (3.3 m/px) vs SLDEM warped to the same grid
  * resolution matched - both block averaged to the SLDEM sampling (~59 m),
    which isolates the resolution effect (hypothesis H1) from real terrain
    differences.
"""
import csv
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "week4"
DEM = OUT / "nac_dem.tif"
REF = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
ERR = OUT / "nac_intersection_err.tif"
SLDEM_PX_M = 59.2          # native sampling of SLDEM2015 (512 ppd)


def open_raster(path):
    """Open a raster, returning None if it is missing or has no bands."""
    try:
        ds = gdal.Open(str(path))
    except Exception:
        return None
    if ds is None or ds.RasterCount < 1 or ds.RasterXSize < 1 or ds.RasterYSize < 1:
        return None
    return ds


def read_band(path):
    ds = gdal.Open(str(path))
    if ds is None:
        return None, None
    return ds.GetRasterBand(1).ReadAsArray().astype("float64"), ds


def block_mean(arr, valid, factor):
    """Average arr over factor x factor blocks, ignoring invalid pixels."""
    ny, nx = arr.shape
    ny2, nx2 = (ny // factor) * factor, (nx // factor) * factor
    a = np.where(valid, arr, 0.0)[:ny2, :nx2].reshape(ny2 // factor, factor, nx2 // factor, factor)
    c = valid[:ny2, :nx2].astype("float64").reshape(ny2 // factor, factor, nx2 // factor, factor)
    cnt = c.sum(axis=(1, 3))
    tot = a.sum(axis=(1, 3))
    out = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
    return out, cnt


def stats_block(d, label):
    off = float(np.median(d))
    detr = d - off
    s = {
        f"{label}_n": int(d.size),
        f"{label}_offset_m": round(off, 3),
        f"{label}_mean_m": round(float(d.mean()), 3),
        f"{label}_std_m": round(float(d.std()), 3),
        f"{label}_rmse_raw_m": round(float(np.sqrt((d ** 2).mean())), 3),
        f"{label}_rmse_detrended_m": round(float(np.sqrt((detr ** 2).mean())), 3),
        f"{label}_mae_detrended_m": round(float(np.abs(detr).mean()), 3),
        f"{label}_p1_m": round(float(np.percentile(detr, 1)), 3),
        f"{label}_p99_m": round(float(np.percentile(detr, 99)), 3),
    }
    return s, off


def main() -> None:
    if not DEM.exists():
        raise SystemExit(f"missing {DEM}")
    dem_ds = gdal.Open(str(DEM))
    gt = dem_ds.GetGeoTransform()
    wkt = dem_ds.GetProjection()
    nx, ny = dem_ds.RasterXSize, dem_ds.RasterYSize
    band = dem_ds.GetRasterBand(1)
    dem = band.ReadAsArray().astype("float64")
    nodata = band.GetNoDataValue()
    px = abs(gt[1])
    print(f"NAC DEM : {nx} x {ny} px, {px:.3f} m/px")

    warped = OUT / "sldem_on_nac_grid.tif"
    if open_raster(warped) is None:
        if warped.exists():
            print(f"rebuilding {warped.name} (existing file is unreadable)")
            warped.unlink()
        warped.parent.mkdir(parents=True, exist_ok=True)
        gdal.Warp(str(warped), str(REF), dstSRS=wkt, xRes=px, yRes=px,
                  resampleAlg="bilinear", width=nx, height=ny,
                  outputBounds=(gt[0], gt[3] + ny * gt[5], gt[0] + nx * gt[1], gt[3]),
                  creationOptions=["COMPRESS=DEFLATE"])
    ref_ds = open_raster(warped)
    if ref_ds is None:
        raise SystemExit("could not read the warped SLDEM - delete it and rerun")
    ref = ref_ds.GetRasterBand(1).ReadAsArray().astype("float64")

    valid = np.isfinite(dem) & np.isfinite(ref)
    if nodata is not None:
        valid &= (dem != nodata)
    d = (dem - ref)[valid]
    print(f"common valid pixels: {d.size:,} of {nx*ny:,} ({100*d.size/(nx*ny):.2f}%)")

    out = {}
    s_full, off_full = stats_block(d, "fullres")
    out.update(s_full)
    print("\n[full resolution]")
    for k, v in s_full.items():
        print(f"  {k:32s} {v}")

    factor = max(1, int(round(SLDEM_PX_M / px)))
    nac_b, cnt = block_mean(dem, valid, factor)
    ref_b, _ = block_mean(ref, valid, factor)
    bvalid = np.isfinite(nac_b) & np.isfinite(ref_b) & (cnt > 0.5 * factor * factor)
    db = (nac_b - ref_b)[bvalid]
    print(f"\n[resolution matched: {factor}x{factor} block average -> "
          f"{factor*px:.1f} m/px, {db.size:,} samples]")
    s_coarse, off_coarse = stats_block(db, "matched")
    out.update(s_coarse)
    for k, v in s_coarse.items():
        print(f"  {k:32s} {v}")

    with (OUT / "nac_vs_sldem_stats.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out))
        w.writeheader()
        w.writerow(out)

    resid = np.full(dem.shape, np.nan)
    resid[valid] = (dem - ref)[valid] - off_full
    np.save(OUT / "nac_vs_sldem_residual.npy", resid)

    err, _ = read_band(ERR)
    if err is not None and err.shape == dem.shape:
        m = valid & np.isfinite(err) & (err > 0)
        if m.sum() > 100:
            print(f"\nintersection error: median {np.median(err[m]):.3f} m, "
                  f"p90 {np.percentile(err[m], 90):.3f} m  (n={m.sum():,})")
    elif err is None:
        print("\n(intersection error file could not be opened - skipped)")

    print(f"\nwrote {OUT / 'nac_vs_sldem_stats.csv'}")


if __name__ == "__main__":
    main()