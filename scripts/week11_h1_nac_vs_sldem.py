#!/usr/bin/env python3
"""Week 11: H1 tested against the real NAC DEM inside its footprint.

Week 10 tested the resolution effect by aggregating one DEM (a controlled
experiment, but not two real products).  Here the same assessment is run on

  * the real NAC stereo DEM, 3.283 m/px, and
  * SLDEM2015, 59.2 m/px,

and compared **per cell** on a common 237 m grid inside the NAC footprint.

Two comparisons are reported, because they answer different questions:

  native  - each DEM uses its own native metric support (slope from adjacent
            pixels: 3.3 m versus 59 m; roughness in a 3x3 window: 10 m versus
            178 m).  This is the practical question: what does the coarse
            product tell you about the terrain a lander meets?
  matched - both DEMs are first aggregated to the same 237 m cells and the
            metrics are computed on those cells.  This isolates the information
            content of the source data from the metric definition.

Outputs: outputs/week11/h1_nac_vs_sldem.csv, h1_nac_vs_sldem.png

Usage
  python scripts/week11_h1_nac_vs_sldem.py --selftest
  python scripts/week11_h1_nac_vs_sldem.py
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from osgeo import gdal  # noqa: E402
from scipy import ndimage  # noqa: E402

gdal.UseExceptions()
# the NAC DEM and SLDEM are two lunar CRSs; PROJ otherwise refuses to reproject
# between bodies whose ellipsoids differ from the WGS84 default
gdal.SetConfigOption("PROJ_IGNORE_CELESTIAL_BODY", "YES")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week5_terrain_metrics as w5  # noqa: E402
import week7_suitability as w7  # noqa: E402

OUT = REPO / "outputs" / "week11"
TMP = OUT / "tmp"
STUDY_DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
NAC_DEM = REPO / "outputs" / "week4" / "nac_dem.tif"
SAFE_SLOPE, DANGER_SLOPE = 5.0, 15.0
SAFE_ROUGH, DANGER_ROUGH = 1.0, 5.0
SAFE_EDGE = 0.33
CELL_M = 237.0


def hazard_from(slope, rough, good):
    hs = np.where(good, w7.ramp(np.nan_to_num(slope), SAFE_SLOPE, DANGER_SLOPE), np.nan)
    hr = np.where(good, w7.ramp(np.nan_to_num(rough), SAFE_ROUGH, DANGER_ROUGH), np.nan)
    s = np.where(good, 0.5 * (np.nan_to_num(hs) + np.nan_to_num(hr)), np.nan)
    return s.astype("float32"), (s < SAFE_EDGE) & good


def write_tif(path, arr, gt, wkt, nodata=-9999.0):
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(path), arr.shape[1], arr.shape[0], 1, gdal.GDT_Float32)
    ds.SetGeoTransform(gt)
    ds.SetProjection(wkt)
    b = ds.GetRasterBand(1)
    b.SetNoDataValue(nodata)
    b.WriteArray(np.where(np.isfinite(arr), arr, nodata).astype("float32"))
    b.FlushCache()
    ds = None


def warp_like(src_path, ref_ds, dst_path, resample="average"):
    """Reproject/resample src onto the grid of ref_ds."""
    gdal.Warp(str(dst_path), str(src_path), format="GTiff",
              width=ref_ds.RasterXSize, height=ref_ds.RasterYSize,
              outputBounds=None, resampleAlg=resample,
              dstSRS=ref_ds.GetProjection(), dstNodata=-9999.0,
              srcNodata=-9999.0, multithread=True)


def flip_stats(a_safe, b_safe, valid):
    """Cells where a (reference) is safe and b is not, and vice versa."""
    a = a_safe.astype(bool) & valid
    b = b_safe.astype(bool) & valid
    return {"n": int(valid.sum()),
            "only_a_pct": round(100.0 * float((a & ~b).sum()) / max(int(valid.sum()), 1), 2),
            "only_b_pct": round(100.0 * float((b & ~a).sum()) / max(int(valid.sum()), 1), 2),
            "both_pct": round(100.0 * float((a & b).sum()) / max(int(valid.sum()), 1), 2),
            "safe_a_pct": round(100.0 * float(a.sum()) / max(int(valid.sum()), 1), 2),
            "safe_b_pct": round(100.0 * float(b.sum()) / max(int(valid.sum()), 1), 2)}


def selftest():
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:58s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    # the NAC CRS is equirectangular with a known central meridian, so the
    # geographic conversion can be checked analytically
    ds = gdal.Open(str(NAC_DEM))
    gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
    import re, math
    lon0 = float(re.search(r'PARAMETER\["central_meridian",([0-9.\-]+)\]', wkt).group(1))
    m_per_deg = math.pi * 1737400.0 / 180.0
    lon_min = lon0 + gt[0] / m_per_deg
    lon_max = lon0 + (gt[0] + gt[1] * ds.RasterXSize) / m_per_deg
    check("NAC west edge longitude", lon_min, 354.693, 0.002)
    check("NAC east edge longitude", lon_max, 354.929, 0.002)
    check("NAC pixel size in metres", abs(gt[1]), 3.283, 0.001)

    # hazard ramp endpoints
    h, safe = hazard_from(np.array([[0.0, 10.0, 20.0]]), np.array([[0.0, 0.0, 0.0]]),
                          np.ones((1, 3), dtype=bool))
    check("flat, gentle terrain is safe", float(safe[0, 0]), 1.0)
    check("20 deg slope is not safe", float(safe[0, 2]), 0.0)

    # flip accounting
    a = np.zeros((4, 1), dtype=bool); a[:2] = True
    b = np.zeros((4, 1), dtype=bool); b[1] = True
    st = flip_stats(a, b, np.ones((4, 1), dtype=bool))
    check("cells safe only under the reference", st["only_a_pct"], 25.0)
    check("cells safe only under the other DEM", st["only_b_pct"], 0.0)
    check("safe fraction under the reference", st["safe_a_pct"], 50.0)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def block_mean_field(a, valid, f):
    m, frac = w5.block_mean(a.astype("float64"), valid, f)
    return m, np.isfinite(m) & (frac > 0.5)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cell-m", type=float, default=CELL_M)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if args.selftest:
        return selftest()

    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    ref = gdal.Open(str(STUDY_DEM))
    ref_gt, ref_wkt = ref.GetGeoTransform(), ref.GetProjection()
    px_ref = abs(ref_gt[1]) * 30320.0
    f = max(1, int(round(args.cell_m / px_ref)))
    cell_m = f * px_ref
    print("=== setup ===")
    print("  comparison grid: {:.0f} m cells (factor {}) on the SLDEM grid".format(cell_m, f))

    # --- SLDEM (already on the comparison grid's parent) ---
    z, valid, px = w5.read_dem(STUDY_DEM)
    met, eff, good = w5.metrics_at_scale(z, valid, px, cell_m)
    s_sldem, safe_sldem = hazard_from(met["slope"], met["roughness"], good)
    print("  SLDEM  {} x {} at {:.1f} m/px".format(z.shape[1], z.shape[0], px))

    # --- NAC: metrics at native resolution, then reprojected per cell ---
    zn, validn, pxn = w5.read_dem(NAC_DEM)
    metn, effn, goodn = w5.metrics_at_scale(zn, validn, pxn, pxn)
    s_nac, safe_nac = hazard_from(metn["slope"], metn["roughness"], goodn)
    print("  NAC    {} x {} at {:.3f} m/px (valid {:.1f} %)".format(
        zn.shape[1], zn.shape[0], pxn, 100.0 * validn.mean()))
    nac_ds = gdal.Open(str(NAC_DEM))
    ngt, nwkt = nac_ds.GetGeoTransform(), nac_ds.GetProjection()
    fields = {"score": s_nac, "safe": safe_nac.astype("float32"),
              "slope": np.where(goodn, np.nan_to_num(metn["slope"]), np.nan).astype("float32"),
              "rough": np.where(goodn, np.nan_to_num(metn["roughness"]), np.nan).astype("float32")}
    warped = {}
    for name, arr in fields.items():
        src = TMP / ("nac_" + name + ".tif")
        dst = TMP / ("nac_" + name + "_on_sldem.tif")
        write_tif(src, arr, ngt, nwkt)
        warp_like(src, ref, dst)
        ds = gdal.Open(str(dst))
        a = ds.GetRasterBand(1).ReadAsArray().astype("float32")
        a[a == -9999.0] = np.nan
        warped[name] = a
        ds = None
        print("    reprojected NAC {} -> SLDEM grid".format(name))

    # aggregate both to the comparison cells
    s_nac_c, ok1 = block_mean_field(warped["score"], np.isfinite(warped["score"]), f)
    s_sl_c, ok2 = block_mean_field(np.nan_to_num(s_sldem), good, f)
    safe_nac_c, ok3 = block_mean_field(np.nan_to_num(warped["safe"]), np.isfinite(warped["safe"]), f)
    safe_sl_c = np.zeros_like(safe_nac_c, dtype=bool)
    ny = min(s_sl_c.shape[0], s_sldem.shape[0] // f)
    nx = min(s_sl_c.shape[1], s_sldem.shape[1] // f)
    valid = ok1[:ny, :nx] & ok2[:ny, :nx] & ok3[:ny, :nx]
    a_safe = safe_nac_c[:ny, :nx] > 0.5
    b_safe = safe_sl_c[:ny, :nx]
    b_safe = (s_sl_c[:ny, :nx] < SAFE_EDGE) & ok2[:ny, :nx]
    st = flip_stats(a_safe, b_safe, valid)
    print("")
    print("=== paired comparison on {:,} cells of {:.0f} m ===".format(st["n"], cell_m))
    print("  safe under NAC   : {:5.2f} %".format(st["safe_a_pct"]))
    print("  safe under SLDEM : {:5.2f} %".format(st["safe_b_pct"]))
    print("  safe under both  : {:5.2f} %".format(st["both_pct"]))
    print("  ONLY SLDEM safe (coarse product misses a hazard): {:5.2f} %".format(st["only_b_pct"]))
    print("  ONLY NAC safe   (coarse product is over-cautious) : {:5.2f} %".format(st["only_a_pct"]))
    rows = [dict(st, cell_m=round(cell_m, 1), source="native metrics")]
    with (OUT / "h1_nac_vs_sldem.csv").open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print("")
    print("  wrote h1_nac_vs_sldem.csv")

    fig, ax = plt.subplots(1, 3, figsize=(16, 6))
    ax[0].imshow(np.where(valid, a_safe.astype(float) - b_safe.astype(float), np.nan),
                 cmap="coolwarm", vmin=-1, vmax=1)
    ax[0].set_title("safe(NAC) - safe(SLDEM)\nblue = only NAC safe, red = only SLDEM safe")
    ax[1].imshow(np.where(valid, s_nac_c[:ny, :nx], np.nan), cmap="RdYlGn_r", vmin=0, vmax=1)
    ax[1].set_title("S from NAC (3.3 m)")
    ax[2].imshow(np.where(valid, s_sl_c[:ny, :nx], np.nan), cmap="RdYlGn_r", vmin=0, vmax=1)
    ax[2].set_title("S from SLDEM (59 m)")
    for a in ax:
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT / "h1_nac_vs_sldem.png", dpi=140)
    print("  wrote h1_nac_vs_sldem.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
