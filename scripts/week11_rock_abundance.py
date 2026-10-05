#!/usr/bin/env python3
"""Week 11, factor 4: add Diviner rock abundance to the suitability model.

Input: a rock-abundance raster covering the study area (percent of surface area
covered by rocks, from the Diviner radiometer product exported through LROC
QuickMap or the USGS map service).  The raster may be in any lunar CRS and any
pixel size; it is reprojected onto the study grid, converted to a hazard layer
and combined with the three existing factors.

The Diviner "Rock Abundance (SAM, 2023)" product (Powell et al. 2023, JGR
Planets, doi:10.1029/2022JE007532; distributed through the UCLA Dataverse,
doi:10.25346/S6/LFAVXU) stores the **fraction** of the surface covered by rocks
larger than about 1-2 m, with a native range of 0 to 1.  Mare backgrounds sit
well below 0.01 and rocky surfaces reach a few tenths, so the default ramp is
0.005 (safe) to 0.10 (danger).  Like every other threshold in this project it is
an assumption, exposed on the command line and subject to the week-8 sensitivity
analysis.

Usage
  python scripts/week11_rock_abundance.py --selftest
  python scripts/week11_rock_abundance.py --ra data/raw/diviner/rock_abundance_rimae_bode.tif
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal  # noqa: E402

gdal.UseExceptions()
gdal.SetConfigOption("PROJ_IGNORE_CELESTIAL_BODY", "YES")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week5_terrain_metrics as w5  # noqa: E402
import week7_suitability as w7  # noqa: E402
import week7_compare_literature as w7c  # noqa: E402

OUT = REPO / "outputs" / "week11"
W7 = REPO / "outputs" / "week7"
STUDY_DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
SAFE_EDGE = 0.33


def resample_to_study(src_path, out_path):
    """Warp any lunar raster onto the study DEM grid (bilinear)."""
    ref = gdal.Open(str(STUDY_DEM))
    gdal.Warp(str(out_path), str(src_path), format="GTiff",
              width=ref.RasterXSize, height=ref.RasterYSize,
              resampleAlg="bilinear", dstSRS=ref.GetProjection(),
              dstNodata=-9999.0, multithread=True)
    ds = gdal.Open(str(out_path))
    a = ds.GetRasterBand(1).ReadAsArray().astype("float32")
    ds = None
    a[a <= -9999.0] = np.nan
    return a


def selftest():
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:58s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    check("ramp at the safe end", float(w7.ramp(np.array([0.002]), 0.005, 0.10)[0]), 0.0)
    check("ramp at the danger end", float(w7.ramp(np.array([0.15]), 0.005, 0.10)[0]), 1.0)
    check("ramp midway", float(w7.ramp(np.array([0.0525]), 0.005, 0.10)[0]), 0.5)

    # synthetic study-area rasters so the whole combine path is exercised
    tmp = OUT / "selftest"
    tmp.mkdir(parents=True, exist_ok=True)
    z, valid, px = w5.read_dem(STUDY_DEM)
    shape = z.shape
    low = np.full(shape, 0.002, dtype="float32")      # mare-like background (0.2 %)
    high = np.full(shape, 0.12, dtype="float32")      # rocky (12 %)
    for name, arr, want_safe in (("low", low, True), ("high", high, False)):
        gt, wkt = w7c.read_raster(STUDY_DEM)[1], gdal.Open(str(STUDY_DEM)).GetProjection()
        ref = gdal.GetDriverByName("GTiff").Create(str(tmp / (name + ".tif")),
                                                   shape[1], shape[0], 1, gdal.GDT_Float32)
        ref.SetGeoTransform(gt)
        ref.SetProjection(wkt)
        ref.GetRasterBand(1).WriteArray(arr)
        ref = None
        back = resample_to_study(tmp / (name + ".tif"), tmp / (name + "_on.tif"))
        h = w7.ramp(np.nan_to_num(back), 0.005, 0.10)
        check("{} rock abundance -> hazard".format(name), float(np.nanmedian(h)),
              0.0 if want_safe else 1.0, 1e-6)

    # a 4-factor equal-weight combination must be at least as hazardous as the
    # 3-factor one when the rock layer is high
    h_rock = np.ones(shape, dtype="float32")
    s3 = np.zeros(shape, dtype="float32")
    s4 = (3 * s3 + h_rock) / 4.0
    check("adding a hazardous rock layer raises the score",
          float(np.nanmean(s4) - np.nanmean(s3)), 0.25, 1e-6)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ra", default="", help="rock abundance raster (any lunar CRS)")
    ap.add_argument("--rock-safe", type=float, default=0.005)
    ap.add_argument("--rock-danger", type=float, default=0.10)
    ap.add_argument("--tag", default="rock4")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if args.selftest:
        return selftest()
    if not args.ra:
        raise SystemExit("--ra is required (export the product first)")

    OUT.mkdir(parents=True, exist_ok=True)
    ra = resample_to_study(args.ra, OUT / "rock_abundance_on_study_grid.tif")
    score, gt = w7c.read_raster(W7 / "suitability_equal.tif")
    classes, _ = w7c.read_raster(W7 / "suitability_classes_equal.tif")
    hs, _ = w7c.read_raster(W7 / "hazard_slope.tif")
    hr, _ = w7c.read_raster(W7 / "hazard_roughness.tif")
    hc, _ = w7c.read_raster(W7 / "hazard_crater.tif")
    ok = np.isfinite(ra) & np.isfinite(hs) & np.isfinite(hr) & np.isfinite(hc)
    h_rock = np.where(ok, w7.ramp(np.nan_to_num(ra), args.rock_safe, args.rock_danger), np.nan)
    s3 = np.where(ok, (np.nan_to_num(hs) + np.nan_to_num(hr) + np.nan_to_num(hc)) / 3.0, np.nan)
    s4 = np.where(ok, (np.nan_to_num(hs) + np.nan_to_num(hr) + np.nan_to_num(hc)
                       + np.nan_to_num(h_rock)) / 4.0, np.nan)
    print("=== rock abundance joins the model ===")
    print("  product: Diviner Rock Abundance (SAM, 2023), fraction of surface")
    print("  ramp {:.4f} -> {:.3f} | valid {:,} px | H_rock mean {:.3f}".format(
        args.rock_safe, args.rock_danger, int(ok.sum()), float(np.nanmean(h_rock))))
    safe3 = (s3 < 0.33) & ok
    safe4 = (s4 < 0.33) & ok
    n = int(ok.sum())
    print("  safe area  3 factors: {:5.2f} %".format(100.0 * safe3.sum() / n))
    print("  safe area  4 factors: {:5.2f} %".format(100.0 * safe4.sum() / n))
    print("  cells that become unsafe when rocks are added: {:5.2f} %".format(
        100.0 * float((safe3 & ~safe4).sum()) / n))
    print("  cells that become safe  (should be 0):         {:5.2f} %".format(
        100.0 * float((safe4 & ~safe3).sum()) / n))

    rows = []
    sites = [("OURS", 353.7617, 11.0840), ("LS1", 355.76, 11.43), ("LS2", 356.56, 12.41),
             ("LS3", 355.78, 12.16), ("LS4", 355.97, 10.43)]
    win = 84
    for label, lon, lat in sites:
        r, c = w7c.to_pixel(gt, lon, lat)
        r0, c0 = max(0, r - win // 2), max(0, c - win // 2)
        sl = (slice(r0, r0 + win), slice(c0, c0 + win))
        ra_win = float(np.nanmean(np.where(ok[sl], h_rock[sl], np.nan)))
        rows.append({"site": label, "lon": lon, "lat": lat,
                     "H_rock_mean": round(ra_win, 4),
                     "S3": round(float(np.nanmean(np.where(ok[sl], s3[sl], np.nan))), 4),
                     "S4": round(float(np.nanmean(np.where(ok[sl], s4[sl], np.nan))), 4)})
    print("")
    print("  {:>6} {:>10} {:>10} {:>9} {:>8} {:>8}".format(
        "site", "lon E", "lat N", "H_rock", "S3", "S4"))
    for r in rows:
        print("  {:>6} {:>10.4f} {:>10.4f} {:>9.3f} {:>8.3f} {:>8.3f}".format(
            r["site"], r["lon"], r["lat"], r["H_rock_mean"], r["S3"], r["S4"]))
    with (OUT / "rock_abundance_summary.csv").open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    w7.write_raster(OUT / ("suitability_" + args.tag + ".tif"), s4, gt,
                    gdal.Open(str(STUDY_DEM)).GetProjection())
    w7.write_raster(OUT / "hazard_rock.tif", h_rock, gt,
                    gdal.Open(str(STUDY_DEM)).GetProjection())
    print("")
    print("  wrote rock_abundance_summary.csv, hazard_rock.tif, suitability_{}.tif".format(args.tag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
