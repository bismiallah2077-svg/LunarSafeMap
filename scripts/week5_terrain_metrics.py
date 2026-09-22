#!/usr/bin/env python3
"""Week 5.2: multi-scale terrain metrics on the NAC DEM and on SLDEM.

The same terrain metrics (slope, curvature, roughness, local relief) are
computed at three physical scales (20 m, 60 m, 200 m) from two DEMs:

  * the 3.28 m/px NAC stereo DEM (high resolution reference)
  * SLDEM2015 at 59 m/px (the product normally used for landing-site work)

Each metric at scale s comes from the DEM block averaged to that scale, so
the comparison answers "can a 60 m product represent the risk a lander or
rover actually experiences?".  scipy.ndimage filters keep memory modest.
"""
import csv
from pathlib import Path

import numpy as np
from osgeo import gdal
from scipy import ndimage

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
W4 = REPO / "outputs" / "week4"
OUT = REPO / "outputs" / "week5"
DEMS = {"NAC_3.28m": W4 / "nac_dem.tif",
        "SLDEM_59m": REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"}
SCALES_M = (20.0, 60.0, 200.0)
SLOPE_THRESHOLDS = (10.0, 15.0, 20.0)


def open_raster(path):
    ds = gdal.Open(str(path))
    if ds is None or ds.RasterCount < 1:
        raise SystemExit("cannot open {}".format(path))
    return ds


MOON_M_PER_DEG = 30320.0        # 2*pi*1737400 m / 360


def read_dem(path):
    """Read a DEM and return (data, valid mask, pixel size in metres).

    Handles both projected DEMs (pixel size already in metres) and the
    selenographic lon/lat DEMs used for SLDEM, whose pixel size is in
    degrees - converting those is essential, otherwise the scale becomes
    0.002 "metres" and every block average collapses the array.
    """
    ds = open_raster(path)
    band = ds.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    z = band.ReadAsArray().astype("float32")
    valid = np.isfinite(z)
    if nodata is not None:
        valid &= z != nodata
    gt = ds.GetGeoTransform()
    px = abs(gt[1])
    if px < 0.01:                      # degrees, not metres
        print("  (geographic grid: {:.6f} deg/px -> {:.2f} m/px on the Moon)"
              .format(px, px * MOON_M_PER_DEG))
        px = px * MOON_M_PER_DEG
    return z, valid, px


def nac_footprint_on(path_dem_like, nac_path):
    """Return a boolean mask on the grid of path_dem_like marking the area
    covered by the NAC DEM, so both DEMs can be compared over the same ground."""
    ref = open_raster(path_dem_like)
    gt = ref.GetGeoTransform()
    w, h = ref.RasterXSize, ref.RasterYSize
    nac = open_raster(nac_path)
    band = nac.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    z = band.ReadAsArray().astype("float32")
    ok = np.isfinite(z)
    if nodata is not None:
        ok &= z != nodata
    tmp = OUT / "_nac_mask.tif"
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(tmp), ok.shape[1], ok.shape[0], 1, gdal.GDT_Byte)
    ds.SetGeoTransform(nac.GetGeoTransform())
    ds.SetProjection(nac.GetProjection())
    ds.GetRasterBand(1).WriteArray(ok.astype("uint8"))
    ds = None
    warped = OUT / "_nac_mask_on_ref.tif"
    gdal.Warp(str(warped), str(tmp), width=w, height=h,
              outputBounds=(gt[0], gt[3] + h * gt[5], gt[0] + w * gt[1], gt[3]),
              dstSRS=ref.GetProjection(), resampleAlg="near")
    m = gdal.Open(str(warped)).GetRasterBand(1).ReadAsArray() > 0
    return m

def block_mean(arr, valid, factor):
    ny, nx = arr.shape
    ny2, nx2 = (ny // factor) * factor, (nx // factor) * factor
    a = np.where(valid, arr, 0.0)[:ny2, :nx2]
    c = valid[:ny2, :nx2].astype("float64")
    a = a.reshape(ny2 // factor, factor, nx2 // factor, factor).sum(axis=(1, 3))
    c = c.reshape(ny2 // factor, factor, nx2 // factor, factor).sum(axis=(1, 3))
    return np.where(c > 0, a / np.maximum(c, 1), np.nan), c / (factor * factor)


def window_stats(zf, good, size=3):
    g = good.astype("float64")
    cnt = ndimage.uniform_filter(g, size=size) * (size * size)
    z0 = np.where(good, zf, 0.0)
    s1 = ndimage.uniform_filter(z0, size=size) * (size * size)
    mean = np.where(cnt > 0, s1 / np.maximum(cnt, 1e-9), np.nan)
    s2 = ndimage.uniform_filter(z0 * z0, size=size) * (size * size)
    var = np.where(cnt > 0, s2 / np.maximum(cnt, 1e-9) - mean ** 2, np.nan)
    std = np.sqrt(np.maximum(var, 0.0))
    mx = ndimage.maximum_filter(np.where(good, zf, -1e30), size=size)
    mn = ndimage.minimum_filter(np.where(good, zf, 1e30), size=size)
    relief = np.where(np.isfinite(mx) & np.isfinite(mn), mx - mn, np.nan)
    return std, relief


def metrics_at_scale(z, valid, px, scale):
    factor = int(round(scale / px))
    if factor < 1:
        return None
    if factor == 1:
        zs, frac, eff = z.astype("float64"), valid.astype("float64"), px
    else:
        zs, frac = block_mean(z, valid, factor)
        eff = factor * px
    good = np.isfinite(zs) & (frac > 0.5)
    zf = np.where(good, zs, np.nan)
    gy, gx = np.gradient(zf)
    slope = np.degrees(np.arctan(np.hypot(gx, gy) / eff))
    curvature = (np.gradient(gx, axis=1) + np.gradient(gy, axis=0)) / eff ** 2
    rough, relief = window_stats(zf, good)
    return {"slope": np.where(good, slope, np.nan),
            "curvature": np.where(good, curvature, np.nan),
            "roughness": np.where(good, rough, np.nan),
            "relief": np.where(good, relief, np.nan)}, eff, good


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    nac_path = DEMS["NAC_3.28m"]
    for name, path in DEMS.items():
        z, valid, px = read_dem(path)
        if name != "NAC_3.28m":
            try:
                foot = nac_footprint_on(path, nac_path)
                valid = valid & foot
                print("  (restricted to the NAC stereo footprint: {:.1f}% of this DEM)"
                      .format(100 * foot.mean()))
            except Exception as exc:
                print("  (footprint mask failed: {})".format(exc))
        print("")
        print("===== {}  ({:.3f} m/px, {}x{}) =====".format(name, px, z.shape[1], z.shape[0]))
        for scale in SCALES_M:
            res = metrics_at_scale(z, valid, px, scale)
            if res is None:
                print("  {:6.0f} m : below the DEM resolution - skipped".format(scale))
                continue
            m, eff, good = res
            row = {"dem": name, "native_px_m": round(px, 3), "scale_m": scale,
                   "effective_px_m": round(eff, 2), "valid_px": int(good.sum())}
            for key, arr in m.items():
                v = arr[np.isfinite(arr)]
                if v.size:
                    row[key + "_mean"] = round(float(v.mean()), 3)
                    row[key + "_p95"] = round(float(np.percentile(v, 95)), 3)
            sl = m["slope"]
            valid_slope = np.isfinite(sl)
            for th in SLOPE_THRESHOLDS:
                frac = float(np.sum((sl >= th) & valid_slope) / max(valid_slope.sum(), 1))
                row["slope_ge_{}_pct".format(int(th))] = round(100 * frac, 2)
            print("  {:6.0f} m : slope mean {:5.2f} deg, p95 {:5.2f} deg | ".format(
                  scale, row["slope_mean"], row["slope_p95"]) +
                  "roughness p95 {:6.2f} m | relief p95 {:7.2f} m".format(
                      row["roughness_p95"], row["relief_p95"]))
            print("             slope >= 10/15/20 deg : {:.1f} / {:.1f} / {:.1f} % of pixels".format(
                  row["slope_ge_10_pct"], row["slope_ge_15_pct"], row["slope_ge_20_pct"]))
            rows.append(row)
    keys = sorted({k for r in rows for k in r})
    order = ["dem", "native_px_m", "scale_m", "effective_px_m", "valid_px"]
    fieldnames = order + [k for k in keys if k not in order]
    out = OUT / "terrain_metrics_multiscale.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    print("")
    print("wrote {}".format(out))


if __name__ == "__main__":
    main()