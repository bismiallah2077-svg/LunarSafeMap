#!/usr/bin/env python3
"""Test whether the NAC DEM and SLDEM are horizontally co-registered.

Method: on a rough surface the residual between two DEMs that are shifted
relative to each other is proportional to the local terrain gradient,

    z_nac(x) - z_sldem(x)  ~  a * dz/dx + b * dz/dy + c

so a least squares fit of the residual against the gradient gives the
misregistration vector (a, b) in metres.  The script then shifts SLDEM by
that vector and reports how much of the residual it explains.
"""
import csv
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "week4"
DEM = OUT / "nac_dem.tif"
REF = OUT / "sldem_on_nac_grid.tif"


def open_raster(path):
    ds = gdal.Open(str(path))
    if ds is None or ds.RasterCount < 1:
        raise SystemExit(f"cannot open {path}")
    return ds


def main() -> None:
    ds = open_raster(DEM)
    gt = ds.GetGeoTransform()
    px = abs(gt[1])
    band = ds.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    dem = band.ReadAsArray().astype("float32")

    # keep the dataset object alive: a band obtained from a temporary dataset
    # becomes invalid as soon as Python collects it
    ref_ds = open_raster(REF)
    ref_band = ref_ds.GetRasterBand(1)
    ref = ref_band.ReadAsArray().astype("float32")
    valid = np.isfinite(dem) & np.isfinite(ref)
    if nodata is not None:
        valid &= dem != nodata
    print(f"grid {dem.shape[1]} x {dem.shape[0]} px, {px:.3f} m/px, valid {valid.mean()*100:.2f}%")

    # terrain gradient of the NAC DEM (metres per metre)
    gy, gx = np.gradient(np.where(valid, dem, np.nan).astype("float64"))
    gx = (gx / px).astype("float32")
    gy = (gy / px).astype("float32")

    # subsample for the fit (every 2nd pixel is plenty)
    m = valid.copy()
    m[::2, :] = False
    good = m & np.isfinite(gx) & np.isfinite(gy)
    print(f"fit samples: {good.sum():,}")

    resid = (dem - ref)[good].astype("float64")
    A = np.column_stack([gx[good].astype("float64"),
                         gy[good].astype("float64"),
                         np.ones(good.sum())])
    coef, *_ = np.linalg.lstsq(A, resid, rcond=None)
    a, b, c = coef
    shift_m = (b, -a)          # (dx, dy) in metres, sign for shifting SLDEM
    predicted = A @ coef
    r_after = resid - predicted
    print(f"\nleast squares residual model:")
    print(f"  a (dz/dx) = {a:12.4f}   -> x shift candidate {b:9.2f} m")
    print(f"  b (dz/dy) = {b:12.4f}   -> y shift candidate {-a:9.2f} m")
    print(f"  c (bias)  = {c:12.4f} m")
    print(f"  RMSE before fit: {np.sqrt((resid**2).mean()):8.3f} m")
    print(f"  RMSE after  fit: {np.sqrt((r_after**2).mean()):8.3f} m")

    # empirical check: roll SLDEM by the fitted shift and recompute
    sx = int(round(b / px))
    sy = int(round(-a / px))
    print(f"\nempirical shift of SLDEM by ({sx}, {sy}) px = ({sx*px:.1f}, {sy*px:.1f}) m")
    ref_shift = np.roll(np.roll(ref, sy, axis=0), sx, axis=1)
    v2 = valid.copy()
    if sy >= 0: v2[:sy, :] = False
    else: v2[sy:, :] = False
    if sx >= 0: v2[:, :sx] = False
    else: v2[:, sx:] = False
    d0 = (dem - ref)[valid]
    d1 = (dem - ref_shift)[v2]
    print(f"  RMSE before shift: {np.sqrt((d0**2).mean()):8.3f} m  (n={d0.size:,})")
    print(f"  RMSE after  shift: {np.sqrt((d1**2).mean()):8.3f} m  (n={d1.size:,})")
    print(f"  median before/after: {np.median(d0):7.3f} / {np.median(d1):7.3f} m")

    # residual versus slope
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    print("\nMAE versus terrain slope (full resolution):")
    rows = []
    for lo, hi in [(0, 2), (2, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 90)]:
        sel = valid & (slope >= lo) & (slope < hi)
        if sel.sum() < 1000:
            continue
        dd = (dem - ref)[sel]
        mae = float(np.abs(dd - np.median(dd)).mean())
        rows.append((f"{lo}-{hi}", int(sel.sum()), round(float(slope[sel].mean()), 2),
                     round(float(dd.mean()), 2), round(mae, 2)))
        print(f"  slope {lo:2d}-{hi:2d} deg : n={sel.sum():>10,}  mean_slope={rows[-1][2]:5.2f}  "
              f"mean_diff={rows[-1][3]:7.2f} m  MAE={mae:7.2f} m")

    with (OUT / "nac_vs_sldem_coregistration.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value"])
        w.writerow(["x_shift_m", round(b, 3)])
        w.writerow(["y_shift_m", round(-a, 3)])
        w.writerow(["bias_m", round(c, 3)])
        w.writerow(["rmse_before_shift_m", round(float(np.sqrt((d0 ** 2).mean())), 3)])
        w.writerow(["rmse_after_shift_m", round(float(np.sqrt((d1 ** 2).mean())), 3)])
    print(f"\nwrote {OUT / 'nac_vs_sldem_coregistration.csv'}")


if __name__ == "__main__":
    main()