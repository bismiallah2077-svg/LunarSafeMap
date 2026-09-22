#!/usr/bin/env python3
"""Week 5.3: spatial structure of the NAC-minus-SLDEM elevation residual.

Three views:
  1. along-track and across-swath profiles (median and IQR per bin);
  2. a coarse median-residual grid, printed as an ASCII map, plus a fitted
     plane so a long-wavelength tilt is separated from local terrain;
  3. residual versus the ASP intersection error.

Outputs: outputs/week5/error_profiles.csv, error_spatial_grid.csv,
         error_spatial_map.png
"""
import csv
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from osgeo import gdal

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
W4 = REPO / "outputs" / "week4"
OUT = REPO / "outputs" / "week5"
DEM = W4 / "nac_dem.tif"
REF = W4 / "sldem_on_nac_grid.tif"
ERR = W4 / "nac_intersection_err.tif"
GRID_CELL_M = 210.0
PROFILE_BINS = 40


def open_raster(path):
    ds = gdal.Open(str(path))
    if ds is None or ds.RasterCount < 1:
        raise SystemExit("cannot open {}".format(path))
    return ds


def read_band(path):
    ds = open_raster(path)
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype("float32")
    return arr, band.GetNoDataValue(), ds


def bin_profile(resid, valid, axis, nbins=PROFILE_BINS):
    """Median and inter-quartile range of the residual along one axis."""
    n = resid.shape[axis]
    edges = np.linspace(0, n, nbins + 1).astype(int)
    centres, med, q1, q3, cnt = [], [], [], [], []
    for i in range(nbins):
        lo, hi = int(edges[i]), int(edges[i + 1])
        if hi - lo < 1:
            continue
        if axis == 0:
            sl, vm = resid[lo:hi, :], valid[lo:hi, :]
        else:
            sl, vm = resid[:, lo:hi], valid[:, lo:hi]
        vals = sl[vm]
        vals = vals[np.isfinite(vals)]
        if vals.size < 50:
            continue
        centres.append(0.5 * (lo + hi))
        med.append(float(np.median(vals)))
        q1.append(float(np.percentile(vals, 25)))
        q3.append(float(np.percentile(vals, 75)))
        cnt.append(int(vals.size))
    return (np.array(centres), np.array(med), np.array(q1), np.array(q3),
            np.array(cnt))


def profile_slope(position_km, med):
    """Least squares slope of a binned profile, in m/km."""
    m = np.isfinite(med)
    if m.sum() < 2:
        return float("nan")
    A = np.column_stack([position_km[m], np.ones(int(m.sum()))])
    coef, *_ = np.linalg.lstsq(A, med[m], rcond=None)
    return float(coef[0])


def coarse_grid(resid, valid, factor):
    """Median residual per factor x factor block (sparse blocks -> nan)."""
    ny, nx = resid.shape
    ny2, nx2 = (ny // factor) * factor, (nx // factor) * factor
    a = resid[:ny2, :nx2].reshape(ny2 // factor, factor, nx2 // factor, factor)
    v = valid[:ny2, :nx2].reshape(ny2 // factor, factor, nx2 // factor, factor)
    a = np.where(v, a, np.nan)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(a, axis=(1, 3))
        cnt = v.sum(axis=(1, 3))
    med[cnt < 0.3 * factor * factor] = np.nan
    return med, cnt


def plane_fit(grid, cell_m):
    """Fit median_resid = a*x + b*y + c on the coarse grid; returns m/km."""
    ny, nx = grid.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    m = np.isfinite(grid)
    if m.sum() < 10:
        return None
    A = np.column_stack([xx[m] * cell_m / 1000.0,
                         yy[m] * cell_m / 1000.0,
                         np.ones(int(m.sum()))])
    coef, *_ = np.linalg.lstsq(A, grid[m], rcond=None)
    return float(coef[0]), float(coef[1]), float(coef[2])


def ascii_map(grid, width=76):
    """Compact ASCII rendering of the coarse residual grid."""
    ny, nx = grid.shape
    step_y = max(1, ny // 18)
    step_x = max(1, nx // width)
    sub = grid[::step_y, ::step_x]
    finite = sub[np.isfinite(sub)]
    if finite.size == 0:
        return "  (no valid cells)"
    lim = float(np.percentile(np.abs(finite), 95)) or 1.0
    chars = " .:-=+*#%@"
    out = []
    for row in sub:
        line = ""
        for v in row:
            if not np.isfinite(v):
                line += " "
            else:
                idx = int(np.clip((v + lim) / (2 * lim) * (len(chars) - 1),
                                  0, len(chars) - 1))
                line += chars[idx]
        out.append("  " + line)
    return "\n".join(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dem, nodata, ds = read_band(DEM)
    px = abs(ds.GetGeoTransform()[1])
    ref, _, _ = read_band(REF)
    valid = np.isfinite(dem) & np.isfinite(ref)
    if nodata is not None:
        valid &= dem != nodata
    resid = np.where(valid, dem - ref, np.nan).astype("float32")
    off = float(np.nanmedian(resid))
    resid -= off
    print("grid {} x {}, {:.3f} m/px, valid {:.1f}%, global offset {:.2f} m"
          .format(resid.shape[1], resid.shape[0], px, 100 * valid.mean(), off))

    print("")
    print("=== along-track profile (long axis of the strip) ===")
    c, med, q1, q3, n = bin_profile(resid, valid, axis=0)
    dist_km = c * px / 1000.0
    step = max(1, len(c) // 10)
    for i in range(0, len(c), step):
        print("  {:7.1f} km : median {:7.2f} m  IQR [{:7.2f}, {:7.2f}]  n={:,}"
              .format(dist_km[i], med[i], q1[i], q3[i], n[i]))

    print("")
    print("=== across-swath profile (short axis) ===")
    c2, med2, q12, q32, n2 = bin_profile(resid, valid, axis=1)
    width_km = c2 * px / 1000.0
    step2 = max(1, len(c2) // 10)
    for i in range(0, len(c2), step2):
        print("  {:7.1f} km : median {:7.2f} m  IQR [{:7.2f}, {:7.2f}]  n={:,}"
              .format(width_km[i], med2[i], q12[i], q32[i], n2[i]))

    with (OUT / "error_profiles.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["axis", "position_km", "median_m", "q25_m", "q75_m", "n"])
        for i in range(len(c)):
            w.writerow(["along_track", round(float(dist_km[i]), 3),
                        round(float(med[i]), 3), round(float(q1[i]), 3),
                        round(float(q3[i]), 3), int(n[i])])
        for i in range(len(c2)):
            w.writerow(["across_swath", round(float(width_km[i]), 3),
                        round(float(med2[i]), 3), round(float(q12[i]), 3),
                        round(float(q32[i]), 3), int(n2[i])])

    factor = max(1, int(round(GRID_CELL_M / px)))
    grid, cnt = coarse_grid(resid, valid, factor)
    cell_m = factor * px
    print("")
    print("=== coarse median-residual map ({:.0f} m cells) ===".format(cell_m))
    print("  symbols: blank = no data, '.'..'@' = NAC below .. above SLDEM")
    print(ascii_map(grid))

    pf = plane_fit(grid, cell_m)
    if pf:
        gx_, gy_, c0 = pf
        # xx = column index = across swath (short axis); yy = row index = along track
        print("  fitted plane (coarse grid): {:+.3f} m/km across swath, {:+.3f} m/km along track"
              .format(gx_, gy_))
        print("  -> across the {:.1f} km swath that is {:+.1f} m end to end"
              .format(grid.shape[1] * cell_m / 1000.0,
                      gx_ * grid.shape[1] * cell_m / 1000.0))
        print("  -> along the {:.1f} km strip that is {:+.1f} m end to end"
              .format(grid.shape[0] * cell_m / 1000.0,
                      gy_ * grid.shape[0] * cell_m / 1000.0))
        print("  cross-check from the 1-D profiles: across {:+.3f} m/km, along {:+.3f} m/km"
              .format(profile_slope(width_km, med2), profile_slope(dist_km, med)))

    with (OUT / "error_spatial_grid.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell_size_m", round(cell_m, 3)])
        w.writerow(["rows", grid.shape[0], "cols", grid.shape[1]])
        for row in grid:
            w.writerow(["" if not np.isfinite(v) else round(float(v), 3)
                        for v in row])

    err, _, _ = read_band(ERR)
    if err.shape == resid.shape:
        m = valid & np.isfinite(err) & (err > 0)
        if int(m.sum()) > 1000:
            r = resid[m]
            e = err[m]
            print("")
            print("=== residual versus intersection error ===")
            print("  correlation coefficient: {:.3f}"
                  .format(float(np.corrcoef(r, e)[0, 1])))
            for lo, hi in [(0, 2), (2, 4), (4, 6), (6, 8), (8, 100)]:
                sel = (e >= lo) & (e < hi)
                if int(sel.sum()) > 1000:
                    print("  intersection error {:>2.0f}-{:<3.0f} m : n={:>10,}  "
                          "median |residual| {:6.2f} m"
                          .format(lo, hi, int(sel.sum()),
                                  float(np.median(np.abs(r[sel])))))

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.2))
    im = axes[0].imshow(grid, cmap="RdBu_r", vmin=-40, vmax=40, aspect="auto")
    axes[0].set_title("median residual per {:.0f} m cell".format(cell_m))
    axes[0].set_xlabel("along track")
    axes[0].set_ylabel("across swath")
    plt.colorbar(im, ax=axes[0], label="NAC - SLDEM (m)")

    axes[1].fill_between(dist_km, q1, q3, alpha=0.3)
    axes[1].plot(dist_km, med, lw=1.6, color="C0")
    axes[1].axhline(0.0, color="k", lw=0.6)
    axes[1].set_title("along-track profile")
    axes[1].set_xlabel("distance (km)")
    axes[1].set_ylabel("NAC - SLDEM (m)")

    axes[2].fill_between(width_km, q12, q32, alpha=0.3, color="C1")
    axes[2].plot(width_km, med2, lw=1.6, color="C1")
    axes[2].axhline(0.0, color="k", lw=0.6)
    axes[2].set_title("across-swath profile")
    axes[2].set_xlabel("distance (km)")

    fig.tight_layout()
    fig.savefig(str(OUT / "error_spatial_map.png"), dpi=150)
    print("")
    print("wrote error_profiles.csv, error_spatial_grid.csv and error_spatial_map.png in {}"
          .format(OUT))


if __name__ == "__main__":
    main()
