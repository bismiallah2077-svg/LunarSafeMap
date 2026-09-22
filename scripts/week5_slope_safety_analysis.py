#!/usr/bin/env python3
"""Week 5 opener: does SLDEM resolve the slope that matters for landing safety?

Week 4 showed that the NAC DEM and SLDEM2015 agree to ~4 m on gentle terrain
but diverge by ~90 m on the steepest crater walls.  Slope is the metric that
actually drives landing-site safety, so this script:

  1. resamples both DEMs to the SLDEM sampling (~59 m) and compares the slope
     fields, including how many pixels cross safety thresholds (10/15/20 deg)
     in one DEM but not the other;
  2. fits an affine residual model (scale, rotation, shear, shift) to rule out
     a spatially varying misregistration as the cause.

Run at the start of week 5.
"""
import csv
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "week5"
W4 = REPO / "outputs" / "week4"
DEM = W4 / "nac_dem.tif"
REF = W4 / "sldem_on_nac_grid.tif"
SLDEM_PX_M = 59.2
THRESHOLDS = (10.0, 15.0, 20.0)


def open_raster(path):
    ds = gdal.Open(str(path))
    if ds is None or ds.RasterCount < 1:
        raise SystemExit(f"cannot open {path}")
    return ds


def block_mean(arr, valid, factor):
    ny, nx = arr.shape
    ny2, nx2 = (ny // factor) * factor, (nx // factor) * factor
    a = np.where(valid, arr, 0.0)[:ny2, :nx2].reshape(ny2 // factor, factor, nx2 // factor, factor)
    c = valid[:ny2, :nx2].astype("float64").reshape(ny2 // factor, factor, nx2 // factor, factor)
    cnt = c.sum(axis=(1, 3))
    tot = a.sum(axis=(1, 3))
    return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan), cnt


def slope_deg(z, px):
    gy, gx = np.gradient(z)
    return np.degrees(np.arctan(np.hypot(gx / px, gy / px)))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ds = open_raster(DEM)
    gt = ds.GetGeoTransform()
    px = abs(gt[1])
    nodata = ds.GetRasterBand(1).GetNoDataValue()
    dem = ds.GetRasterBand(1).ReadAsArray().astype("float32")
    ref_ds = open_raster(REF)
    ref = ref_ds.GetRasterBand(1).ReadAsArray().astype("float32")

    valid = np.isfinite(dem) & np.isfinite(ref)
    if nodata is not None:
        valid &= dem != nodata

    factor = max(1, int(round(SLDEM_PX_M / px)))
    coarse_px = factor * px
    nac_c, cnt = block_mean(dem, valid, factor)
    ref_c, _ = block_mean(ref, valid, factor)
    good = np.isfinite(nac_c) & np.isfinite(ref_c) & (cnt > 0.5 * factor * factor)
    print(f"matched grid: {coarse_px:.1f} m/px, usable blocks {good.sum():,}")

    nac_i = np.where(good, nac_c, np.nan)
    ref_i = np.where(good, ref_c, np.nan)
    s_nac = slope_deg(nac_i, coarse_px)
    s_ref = slope_deg(ref_i, coarse_px)
    ok = np.isfinite(s_nac) & np.isfinite(s_ref)
    ds_ = (s_nac - s_ref)[ok]
    print("\nslope comparison (matched resolution)")
    print(f"  NAC  slope: mean {s_nac[ok].mean():6.2f} deg, p95 {np.percentile(s_nac[ok], 95):6.2f} deg")
    print(f"  SLDEM slope: mean {s_ref[ok].mean():6.2f} deg, p95 {np.percentile(s_ref[ok], 95):6.2f} deg")
    print(f"  difference : median {np.median(ds_):6.2f} deg, MAE {np.abs(ds_).mean():6.2f} deg, "
          f"RMSE {np.sqrt((ds_ ** 2).mean()):6.2f} deg")

    rows = []
    print("\nthreshold crossings (how often the two DEMs disagree about safety)")
    for th in THRESHOLDS:
        unsafe_nac = s_nac >= th
        unsafe_ref = s_ref >= th
        miss = ok & unsafe_nac & ~unsafe_ref      # SLDEM says safe, NAC says not
        false_alarm = ok & ~unsafe_nac & unsafe_ref
        frac_safe_sldem = miss.sum() / max((ok & unsafe_nac).sum(), 1)
        print(f"  {th:4.0f} deg: NAC steeper {int(unsafe_nac[ok].sum()):>8,} px | "
              f"missed by SLDEM {int(miss.sum()):>8,} ({100*frac_safe_sldem:5.1f}% of them) | "
              f"SLDEM-only steep {int(false_alarm.sum()):>8,} px")
        rows.append({"threshold_deg": th, "nac_steeper_px": int(unsafe_nac[ok].sum()),
                     "missed_by_sldem_px": int(miss.sum()),
                     "pct_of_steep_missed": round(100 * frac_safe_sldem, 2),
                     "sldem_only_steep_px": int(false_alarm.sum())})
    with (OUT / "slope_threshold_crossings.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # affine residual model: residual ~ gradient terms modulated linearly in x,y
    print("\naffine (scale / rotation / shear) residual model")
    gy, gx = np.gradient(np.where(valid, dem, np.nan).astype("float64"))
    gx = gx / px
    gy = gy / px
    step = 4
    sel = np.zeros_like(valid, dtype=bool)
    sel[::step, ::step] = True
    sel &= valid & np.isfinite(gx) & np.isfinite(gy)
    rr, cc = np.nonzero(sel)
    x = (cc - cc.mean()) * px
    y = (rr - rr.mean()) * px
    resid = (dem - ref)[sel].astype("float64")
    A = np.column_stack([gx[sel], x * gx[sel], y * gx[sel],
                         gy[sel], x * gy[sel], y * gy[sel],
                         np.ones(sel.sum())])
    coef, *_ = np.linalg.lstsq(A, resid, rcond=None)
    after = resid - A @ coef
    print(f"  samples: {sel.sum():,}")
    print(f"  RMSE before {np.sqrt((resid ** 2).mean()):8.3f} m -> after "
          f"{np.sqrt((after ** 2).mean()):8.3f} m")
    print(f"  scale/shear terms (per metre): ax={coef[1]:.3e} ay={coef[2]:.3e} "
          f"bx={coef[4]:.3e} by={coef[5]:.3e}")
    print(f"  bias {coef[6]:.3f} m")
    with (OUT / "affine_residual_model.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["term", "value"])
        for name, v in zip(["gx", "x*gx", "y*gx", "gy", "x*gy", "y*gy", "bias"], coef):
            w.writerow([name, float(v)])
        w.writerow(["rmse_before_m", float(np.sqrt((resid ** 2).mean()))])
        w.writerow(["rmse_after_m", float(np.sqrt((after ** 2).mean()))])

    np.save(OUT / "slope_nac.npy", s_nac)
    np.save(OUT / "slope_sldem.npy", s_ref)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()