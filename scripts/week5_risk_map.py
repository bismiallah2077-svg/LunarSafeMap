#!/usr/bin/env python3
"""Week 5.4: first-pass landing risk map from terrain metrics.

Rule (deliberately simple and explicit so it can be audited):

  danger  : slope >= SLOPE_THR  or  roughness >= ROUGH_THR
  caution : slope >= CAUTION_FRAC * SLOPE_THR  or  roughness >= CAUTION_FRAC * ROUGH_THR
  safe    : everything else

Two things are compared:

  * the same rule applied at the *same support* (60 m blocks) on the NAC DEM
    and on SLDEM, so the two risk maps are like for like;
  * the NAC DEM at its own resolution (20 m), which shows the hazard that a
    60 m product cannot represent at all.

Pixels whose ASP intersection error exceeds ERR_MAX are masked out first -
week 5.3 showed that the 0.08 percent of pixels above 8 m carry residuals of
hundreds of metres and would otherwise dominate any statistic.

Also produced: a threshold sensitivity sweep, because the "safe area" is a
function of the thresholds as much as of the data.
"""
import csv
import warnings
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
W4 = REPO / "outputs" / "week4"
OUT = REPO / "outputs" / "week5"
NAC_DEM = W4 / "nac_dem.tif"
NAC_ERR = W4 / "nac_intersection_err.tif"
SLDEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"

MOON_M_PER_DEG = 30320.0
ERR_MAX = 8.0                 # metres; matching failures are masked out
SLOPE_THR = 15.0              # degrees, lander / rover limit
ROUGH_THR = 2.0               # metres, high-pass roughness (see residual_roughness)
ROUGH_WINDOW_M = 180.0        # common window for the NAC / SLDEM comparison
ROUGH_WINDOW_FINE_M = 20.0    # fine window reported for the NAC only
CAUTION_FRAC = 0.75
SUPPORTS_M = (20.0, 60.0)     # block size the metrics are computed at
SLOPE_SWEEP = (10.0, 15.0, 20.0)
ROUGH_SWEEP = (1.0, 2.0, 5.0)

CLASS_SAFE, CLASS_CAUTION, CLASS_DANGER, CLASS_NODATA = 0, 1, 2, 255


def open_raster(path):
    ds = gdal.Open(str(path))
    if ds is None or ds.RasterCount < 1:
        raise SystemExit("cannot open {}".format(path))
    return ds


def read_dem(path):
    """Return (z, valid, px_native, px_metres, gt, wkt).

    px_native keeps the units of the file (degrees for the SLDEM grid,
    metres for the projected NAC DEM) so the geotransform can be rebuilt
    correctly; px_metres is used for the physical scale comparisons.
    """
    ds = open_raster(path)
    band = ds.GetRasterBand(1)
    z = band.ReadAsArray().astype("float32")
    valid = np.isfinite(z)
    nd = band.GetNoDataValue()
    if nd is not None:
        valid &= z != nd
    gt = ds.GetGeoTransform()
    px_native = abs(gt[1])
    px_metres = px_native * MOON_M_PER_DEG if px_native < 0.01 else px_native
    return z, valid, px_native, px_metres, gt, ds.GetProjection()


def block_mean(arr, valid, factor):
    ny, nx = arr.shape
    ny2, nx2 = (ny // factor) * factor, (nx // factor) * factor
    a = np.where(valid, arr, 0.0)[:ny2, :nx2]
    c = valid[:ny2, :nx2].astype("float64")
    a = a.reshape(ny2 // factor, factor, nx2 // factor, factor).sum(axis=(1, 3))
    c = c.reshape(ny2 // factor, factor, nx2 // factor, factor).sum(axis=(1, 3))
    return np.where(c > 0, a / np.maximum(c, 1), np.nan), c / (factor * factor)


def residual_roughness(z, valid, size=3):
    """High-pass roughness: RMS of z minus its local mean inside a window.

    A tilted plane gives exactly zero, so this measures deviation from a smooth
    surface rather than the local relief that the slope term already captures.
    """
    from scipy import ndimage
    g = valid.astype("float64")
    cnt = ndimage.uniform_filter(g, size=size) * (size * size)
    z0 = np.where(valid, z, 0.0)
    s1 = ndimage.uniform_filter(z0, size=size) * (size * size)
    mean = np.where(cnt > 0, s1 / np.maximum(cnt, 1e-9), np.nan)
    r = np.where(valid, z - mean, 0.0)
    s2 = ndimage.uniform_filter(r * r, size=size) * (size * size)
    with np.errstate(invalid="ignore"):
        rms = np.sqrt(np.maximum(np.where(cnt > 0, s2 / np.maximum(cnt, 1e-9), np.nan), 0.0))
    rms = np.where(valid, rms, np.nan)
    b = size // 2
    if b > 0:
        rms[:b, :] = np.nan
        rms[-b:, :] = np.nan
        rms[:, :b] = np.nan
        rms[:, -b:] = np.nan
    return rms


def metrics(z, valid, px, support_m, rough_window_m=20.0):
    """Slope at the requested support, roughness over a fixed physical window.

    The slope comes from the surface block averaged to support_m, but the
    roughness is measured on the *native* grid with a window of
    rough_window_m: block averaging first would average away the very
    small-scale variability roughness is meant to capture.

    Returns (slope, roughness, effective pixel size, validity, rough_window_px).
    """
    factor = max(1, int(round(support_m / px)))
    if factor == 1:
        zs, frac, eff = z.astype("float64"), valid.astype("float64"), px
    else:
        zs, frac = block_mean(z, valid, factor)
        eff = factor * px
    good = np.isfinite(zs) & (frac > 0.5)
    zf = np.where(good, zs, np.nan)
    gy, gx = np.gradient(zf)
    slope = np.degrees(np.arctan(np.hypot(gx, gy) / eff))

    win = max(3, int(round(rough_window_m / px)))
    if win % 2 == 0:
        win += 1
    zn = np.where(valid, z.astype("float64"), np.nan)
    rn = residual_roughness(zn, valid, size=win)
    if factor == 1:
        rough, _ = rn, frac
    else:
        rough, _ = block_mean(np.nan_to_num(rn, nan=0.0), valid & np.isfinite(rn), factor)
    rough = np.where(good, rough, np.nan)
    return (np.where(good, slope, np.nan), rough, eff, good, win * px)


def classify(slope, rough, valid, slope_thr=SLOPE_THR, rough_thr=ROUGH_THR,
             caution_frac=CAUTION_FRAC):
    """Return an integer class array (0 safe, 1 caution, 2 danger, 255 nodata)."""
    cls = np.full(slope.shape, CLASS_NODATA, dtype=np.uint8)
    ok = valid & np.isfinite(slope) & np.isfinite(rough)
    danger = ok & ((slope >= slope_thr) | (rough >= rough_thr))
    caution = ok & (~danger) & ((slope >= caution_frac * slope_thr) |
                                (rough >= caution_frac * rough_thr))
    cls[ok] = CLASS_SAFE
    cls[caution] = CLASS_CAUTION
    cls[danger] = CLASS_DANGER
    return cls


def fractions(cls):
    """Fraction of classified (non-nodata) pixels in each class, in percent."""
    ok = cls != CLASS_NODATA
    n = float(ok.sum())
    if n == 0:
        return {"safe_pct": 0.0, "caution_pct": 0.0, "danger_pct": 0.0, "n": 0}
    return {
        "safe_pct": round(100.0 * float((cls == CLASS_SAFE).sum()) / n, 2),
        "caution_pct": round(100.0 * float((cls == CLASS_CAUTION).sum()) / n, 2),
        "danger_pct": round(100.0 * float((cls == CLASS_DANGER).sum()) / n, 2),
        "n": int(n),
    }


def footprint_on(ref_shape, ref_gt, ref_wkt, mask_src, mask_gt, mask_wkt,
                 mask_arr):
    """Warp a boolean mask onto the reference grid (nearest neighbour)."""
    tmp = OUT / "_risk_mask_src.tif"
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(tmp), mask_arr.shape[1], mask_arr.shape[0], 1,
                    gdal.GDT_Byte)
    ds.SetGeoTransform(mask_gt)
    ds.SetProjection(mask_wkt)
    ds.GetRasterBand(1).WriteArray(mask_arr.astype(np.uint8))
    ds = None
    warped = OUT / "_risk_mask_warped.tif"
    gdal.Warp(str(warped), str(tmp), width=ref_shape[1], height=ref_shape[0],
              outputBounds=(ref_gt[0], ref_gt[3] + ref_shape[0] * ref_gt[5],
                            ref_gt[0] + ref_shape[1] * ref_gt[1], ref_gt[3]),
              dstSRS=ref_wkt, resampleAlg="near")
    mds = gdal.Open(str(warped))
    if mds is None or mds.RasterCount < 1:
        raise RuntimeError("could not open the warped mask")
    band = mds.GetRasterBand(1)
    return band.ReadAsArray() > 0


def write_class_tif(path, cls, work_gt, wkt):
    """Write a uint8 class raster using the working grid's geotransform."""
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(path), cls.shape[1], cls.shape[0], 1, gdal.GDT_Byte)
    ds.SetGeoTransform(work_gt)
    ds.SetProjection(wkt)
    ds.GetRasterBand(1).WriteArray(cls)
    ds.GetRasterBand(1).SetNoDataValue(CLASS_NODATA)
    ds = None


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    nac, nac_valid, nac_px_native, nac_px, nac_gt, nac_wkt = read_dem(NAC_DEM)
    edata = open_raster(NAC_ERR)
    err_band = edata.GetRasterBand(1)
    err = err_band.ReadAsArray().astype("float32")
    bad = (~np.isfinite(err)) | (err <= 0) | (err > ERR_MAX)
    n_before = int(nac_valid.sum())
    nac_valid = nac_valid & (~bad)
    print("NAC DEM {} x {} px, {:.3f} m/px".format(nac.shape[1], nac.shape[0], nac_px))
    print("masked by intersection error > {:.1f} m: {:,} px removed ({:.3f}%)"
          .format(ERR_MAX, n_before - int(nac_valid.sum()),
                  100.0 * (n_before - int(nac_valid.sum())) / max(n_before, 1)))

    sldem, sl_valid, sl_px_native, sl_px, sl_gt, sl_wkt = read_dem(SLDEM)
    print("SLDEM    {} x {} px, {:.3f} m/px".format(sldem.shape[1], sldem.shape[0], sl_px))

    keep = {}
    print("")
    print("=== risk classes at a common 60 m support (slope >= {:.0f} deg or roughness >= {:.1f} m) ==="
          .format(SLOPE_THR, ROUGH_THR))
    print("  {:12s} {:>10s} {:>10s} {:>10s} {:>12s}".format(
        "DEM", "safe %", "caution %", "danger %", "n px"))
    rows = []
    for label, z, valid, px, px_native, gt, wkt in (
            ("NAC", nac, nac_valid, nac_px, nac_px_native, nac_gt, nac_wkt),
            ("SLDEM", sldem, sl_valid, sl_px, sl_px_native, sl_gt, sl_wkt)):
        for support in SUPPORTS_M:
            if support < 0.9 * px:
                print("  {:12s} {:>10s}".format(label + " @{:.0f} m".format(support),
                                                "below DEM resolution"))
                continue
            slope, rough, eff, good, rwin = metrics(z, valid, px, support,
                                                     rough_window_m=ROUGH_WINDOW_M)
            _factor = max(1, int(round(support / px)))
            _step = px_native * _factor          # native units (deg or m)
            work_gt = (gt[0], _step, 0.0, gt[3], 0.0, -_step)
            cls = classify(slope, rough, good)
            f = fractions(cls)
            rv = rough[np.isfinite(rough)]
            print("  {:12s} {:10.2f} {:10.2f} {:10.2f} {:12,}".format(
                label + " @{:.0f} m".format(eff), f["safe_pct"], f["caution_pct"],
                f["danger_pct"], f["n"]))
            print("               roughness (window {:.0f} m) p50/p90/p99: {:.2f} / {:.2f} / {:.2f} m"
                  .format(rwin, float(np.percentile(rv, 50)),
                          float(np.percentile(rv, 90)), float(np.percentile(rv, 99))))
            if label == "NAC":
                _s2, rf, _e2, _g2, rwin_f = metrics(z, valid, px, support,
                                                    rough_window_m=ROUGH_WINDOW_FINE_M)
                rvf = rf[np.isfinite(rf)]
                print("               roughness (window {:.0f} m, what SLDEM cannot resolve) "
                      "p50/p90/p99: {:.2f} / {:.2f} / {:.2f} m"
                      .format(rwin_f, float(np.percentile(rvf, 50)),
                              float(np.percentile(rvf, 90)),
                              float(np.percentile(rvf, 99))))
            rows.append({"dem": label, "support_m": round(eff, 2),
                         "slope_thr_deg": SLOPE_THR, "rough_thr_m": ROUGH_THR,
                         "safe_pct": f["safe_pct"], "caution_pct": f["caution_pct"],
                         "danger_pct": f["danger_pct"], "n_px": f["n"]})
            keep[(label, support)] = (slope, rough, eff, good, cls, work_gt, wkt)

    print("")
    print("=== threshold sensitivity: danger area, same 60 m support ===")
    print("  {:>10s} {:>10s} {:>12s} {:>12s}".format("slope thr", "rough thr",
                                                     "NAC @60 m", "SLDEM @60 m"))
    sweep_rows = []
    combos = [(t, ROUGH_THR) for t in SLOPE_SWEEP] + \
             [(SLOPE_THR, r) for r in ROUGH_SWEEP if r != ROUGH_THR]
    for s_thr, r_thr in combos:
        vals = {}
        for label in ("NAC", "SLDEM"):
            if (label, 60.0) not in keep:
                vals[label] = None
                continue
            slope, rough, eff, good, _cls, _gt, _wkt = keep[(label, 60.0)]
            f = fractions(classify(slope, rough, good, slope_thr=s_thr,
                                   rough_thr=r_thr))
            vals[label] = f["danger_pct"]
            sweep_rows.append({"dem": label, "support_m": round(eff, 2),
                               "slope_thr_deg": s_thr, "rough_thr_m": r_thr,
                               "danger_pct": f["danger_pct"]})
        print("  {:10.0f} {:10.1f} {:>12s} {:>12s}".format(
            s_thr, r_thr,
            "{:.1f} %".format(vals["NAC"]) if vals.get("NAC") is not None else "-",
            "{:.1f} %".format(vals["SLDEM"]) if vals.get("SLDEM") is not None else "-"))

    print("")
    print("=== fair comparison: SLDEM limited to the NAC stereo footprint (60 m) ===")
    nac_ok = nac_valid.astype(np.uint8)
    if ("SLDEM", 60.0) in keep and ("NAC", 60.0) in keep:
        slope_s, rough_s, eff_s, good_s, cls_s, gt_s, wkt_s = keep[("SLDEM", 60.0)]
        foot = footprint_on(slope_s.shape, gt_s, wkt_s, nac_ok, nac_gt, nac_wkt, nac_ok)
        frac_foot = float(foot.mean())
        if frac_foot <= 1e-6 or frac_foot >= 1.0 - 1e-6:
            print("  WARNING: the NAC footprint mask covers {:.4f} of the SLDEM grid -"
                  .format(frac_foot))
            print("           check that both CRS are handled in the same units")
        good_r = good_s & foot
        f_all = fractions(cls_s)
        f_res = fractions(classify(slope_s, rough_s, good_r))
        print("  SLDEM whole scene   : safe {:.2f} %, caution {:.2f} %, danger {:.2f} %"
              .format(f_all["safe_pct"], f_all["caution_pct"], f_all["danger_pct"]))
        print("  SLDEM NAC footprint : safe {:.2f} %, caution {:.2f} %, danger {:.2f} %"
              .format(f_res["safe_pct"], f_res["caution_pct"], f_res["danger_pct"]))
        rows.append({"dem": "SLDEM_footprint", "support_m": round(eff_s, 2),
                     "slope_thr_deg": SLOPE_THR, "rough_thr_m": ROUGH_THR,
                     "safe_pct": f_res["safe_pct"], "caution_pct": f_res["caution_pct"],
                     "danger_pct": f_res["danger_pct"], "n_px": f_res["n"]})

    with (OUT / "risk_classes.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    if sweep_rows:
        with (OUT / "risk_threshold_sweep.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sweep_rows[0]))
            w.writeheader()
            w.writerows(sweep_rows)

    if ("NAC", 20.0) in keep:
        _s, _r, eff_n, _g, cls_n, gt_n, wkt_n = keep[("NAC", 20.0)]
        write_class_tif(OUT / "risk_map_nac_20m.tif", cls_n, gt_n, wkt_n)
        print("")
        print("wrote {}".format(OUT / "risk_map_nac_20m.tif"))
    if ("SLDEM", 60.0) in keep:
        _s, _r, eff_s2, _g, cls_s2, gt_s2, wkt_s2 = keep[("SLDEM", 60.0)]
        write_class_tif(OUT / "risk_map_sldem_60m.tif", cls_s2, gt_s2, wkt_s2)
        print("wrote {}".format(OUT / "risk_map_sldem_60m.tif"))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(["#2a9d3f", "#e8b800", "#c1272d", "#dddddd"])
        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        for ax, key, title in ((axes[0], ("NAC", 20.0), "NAC DEM, 20 m support"),
                               (axes[1], ("SLDEM", 60.0), "SLDEM, 60 m support")):
            if key in keep:
                _s, _r, _e, _g, cls, _gt, _wkt = keep[key]
                ax.imshow(cls, cmap=cmap, vmin=0, vmax=3, aspect="auto",
                          interpolation="nearest")
            ax.set_title(title)
            ax.set_xticks([])
            ax.set_yticks([])
        fig.suptitle("first-pass risk map: green = safe, yellow = caution, red = danger")
        fig.tight_layout()
        fig.savefig(str(OUT / "risk_map.png"), dpi=150)
        print("wrote {}".format(OUT / "risk_map.png"))
    except Exception as exc:
        print("(figure skipped: {})".format(exc))

    print("")
    print("wrote risk_classes.csv and risk_threshold_sweep.csv in {}".format(OUT))


if __name__ == "__main__":
    main()
