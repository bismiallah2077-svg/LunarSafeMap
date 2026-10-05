#!/usr/bin/env python3
"""Week 9.1: quantitative case studies for the discussion section.

The discussion needs three kinds of evidence that the maps alone do not give:

  1. *why* each named site scores the way it does - the actual slope, roughness
     and crater population inside its 5 km window, not just the final number;
  2. which parts of the study area are **robustly safe** (safe in every Monte
     Carlo draw) versus **parameter-dependent** (0.1 < P(safe) < 0.9);
  3. where the parameter-dependent regions actually are, with terrain attached,
     so the text can say something geological instead of "some areas are
     uncertain".

Outputs: outputs/week9/case_sites.csv, case_regions.csv, case_studies.png

Usage
  python scripts/week9_case_studies.py --selftest
  python scripts/week9_case_studies.py --tag k15 --top 6
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from osgeo import gdal  # noqa: E402
from scipy import ndimage  # noqa: E402

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week7_suitability as w7  # noqa: E402
import week7_compare_literature as w7c  # noqa: E402
import week5_terrain_metrics as w5  # noqa: E402

W7 = REPO / "outputs" / "week7"
W8 = REPO / "outputs" / "week8"
OUT = REPO / "outputs" / "week9"
SITES_CSV = REPO / "configs" / "landing_sites.csv"
CATALOGUE = REPO / "outputs" / "week6" / "craters_detected.geojson"
MOON_M_PER_DEG = 30320.0
SITE_KM = 5.0
DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"


def centre_km(a_lon, a_lat, b_lon, b_lat):
    dlat = (b_lat - a_lat) * MOON_M_PER_DEG / 1000.0
    dlon = (b_lon - a_lon) * MOON_M_PER_DEG / 1000.0 * math.cos(
        math.radians(0.5 * (a_lat + b_lat)))
    return math.hypot(dlat, dlon)


def window_slice(gt, lon, lat, site_km, shape):
    """Pixel bounds of the site window, clipped to the raster."""
    r, c = w7c.to_pixel(gt, lon, lat)
    half = int(round(site_km * 1000.0 / (abs(gt[1]) * MOON_M_PER_DEG) / 2.0))
    r0, r1 = max(0, r - half), min(shape[0], r + half + 1)
    c0, c1 = max(0, c - half), min(shape[1], c + half + 1)
    return r, c, (slice(r0, r1), slice(c0, c1))


def site_table(sites, gt, shape, slope, rough, crater_h, cats, win_km):
    rows = []
    for s in sites:
        r, c, sl = window_slice(gt, s["lon"], s["lat"], win_km, shape)
        if not (0 <= r < shape[0] and 0 <= c < shape[1]):
            continue
        sl_win = slope[sl]
        rg_win = rough[sl]
        cr_win = crater_h[sl]
        # read_catalogue returns (lat, lon, diam_km) tuples
        near = min(cats, key=lambda k: centre_km(s["lon"], s["lat"], k[1], k[0]))
        dist = centre_km(s["lon"], s["lat"], near[1], near[0])
        inside = [k for k in cats
                  if centre_km(s["lon"], s["lat"], k[1], k[0]) < win_km / 2.0 * 1.05]
        rows.append({
            "site": s["label"], "lon": round(s["lon"], 4), "lat": round(s["lat"], 4),
            "slope_med_deg": round(float(np.nanmedian(sl_win)), 2),
            "slope_p95_deg": round(float(np.nanpercentile(sl_win, 95)), 2),
            "rough_med_m": round(float(np.nanmedian(rg_win)), 2),
            "rough_p95_m": round(float(np.nanpercentile(rg_win, 95)), 2),
            "crater_haz_mean": round(float(np.nanmean(cr_win)), 3),
            "n_craters_in_window": len(inside),
            "nearest_crater_km": round(dist, 2),
            "nearest_crater_diam_km": round(float(near[2]), 2),
        })
    return rows


def region_table(mask, gt, px_m, slope, rough, top_n, label):
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), dtype="uint8"))
    if n == 0:
        return []
    px_km2 = (px_m / 1000.0) ** 2
    counts = np.bincount(lab.ravel())
    rows = []
    order = np.argsort(counts[1:])[::-1][:top_n] + 1
    for i in order:
        if counts[i] == 0:
            continue
        rr, cc = np.where(lab == i)
        r_c, c_c = float(rr.mean()), float(cc.mean())
        lon = gt[0] + gt[1] * (c_c + 0.5)
        lat = gt[3] + gt[5] * (r_c + 0.5)
        rows.append({
            "kind": label, "area_km2": round(float(counts[i]) * px_km2, 1),
            "lon": round(lon, 4), "lat": round(lat, 4),
            "slope_med_deg": round(float(np.nanmedian(slope[lab == i])), 2),
            "rough_med_m": round(float(np.nanmedian(rough[lab == i])), 2),
            "n_px": int(counts[i]),
        })
    return rows


def selftest():
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:56s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    gt = (353.0, 0.001953125, 0.0, 13.0, 0.0, -0.001953125)
    shape = (2561, 3073)
    r, c, sl = window_slice(gt, 355.76, 11.43, 5.0, shape)
    rows = sl[0].stop - sl[0].start
    check("5 km window is 84 px on a 59.2 m grid", rows, 84, 1)

    cost = np.zeros(shape, dtype="float32")
    a = np.ones((90, 90), dtype="float32") * 10.0
    cost[sl] = a[:sl[0].stop - sl[0].start, :sl[1].stop - sl[1].start]
    check("window median of a constant field", float(np.nanmedian(cost[sl])), 10.0)

    # two blobs: one 100 px, one 400 px -> the larger one must be reported first
    m = np.zeros((50, 50), dtype=bool)
    m[5:15, 5:15] = True
    m[25:45, 25:45] = True
    gt2 = (353.0, 0.001953125, 0.0, 13.0, 0.0, -0.001953125)
    regs = region_table(m, gt2, 59.22, np.zeros((50, 50), "float32"),
                        np.zeros((50, 50), "float32"), 2, "test")
    check("largest blob first", regs[0]["n_px"], 400, 0)
    check("second blob", regs[1]["n_px"], 100, 0)

    check("1 deg latitude on the Moon", centre_km(0.0, 0.0, 0.0, 1.0), 30.32, 0.01)
    check("distance to itself", centre_km(355.0, 10.0, 355.0, 10.0), 0.0, 1e-9)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tag", default="k15", help="Monte Carlo run to read probabilities from")
    ap.add_argument("--site-km", type=float, default=SITE_KM)
    ap.add_argument("--top", type=int, default=6, help="regions per category")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        return selftest()

    OUT.mkdir(parents=True, exist_ok=True)
    print("=== inputs ===")
    # Physical terrain metrics (degrees, metres).  A discussion section has to
    # quote quantities, not normalised hazard ramps: the ramps depend on the
    # thresholds, which is exactly what week 8 shows to be uncertain.
    z, valid, px_dem = w5.read_dem(DEM)
    metrics, eff, good = w5.metrics_at_scale(z, valid, px_dem, 60.0)
    slope = np.where(good, metrics["slope"], np.nan).astype("float32")
    rough = np.where(good, metrics["roughness"], np.nan).astype("float32")
    crater_h, gt = w7c.read_raster(W7 / "hazard_crater.tif")
    score, _ = w7c.read_raster(W7 / "suitability_equal.tif")
    p_safe, _ = w7c.read_raster(W8 / ("mc_prob_safe_" + args.tag + ".tif"))
    p_dang, _ = w7c.read_raster(W8 / ("mc_prob_danger_" + args.tag + ".tif"))
    px_m = abs(gt[1]) * MOON_M_PER_DEG
    shape = slope.shape
    print("  grid {} x {} at {:.2f} m/px, terrain support {:.0f} m".format(
        shape[1], shape[0], px_m, eff))
    print("  slope/roughness are physical (deg / m); crater_haz is the 1 km-buffer")
    print("  hazard layer from week 7; probabilities from the {} run".format(args.tag))

    cats = w7.read_catalogue(CATALOGUE)
    sites = []
    with SITES_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(r for r in f if not r.startswith("#")):
            if row.get("lon"):
                sites.append({"label": row["label"].strip(),
                              "lon": float(row["lon"]), "lat": float(row["lat"])})
    best = W7 / "candidate_sites_equal.csv"
    if best.exists():
        with best.open(newline="", encoding="utf-8-sig") as f:
            first = next(csv.DictReader(f))
            sites.append({"label": "OURS(#1 equal)", "lon": float(first["lon"]),
                          "lat": float(first["lat"])})

    print("")
    print("=== why each site scores what it scores ({} km window) ===".format(args.site_km))
    rows = site_table(sites, gt, shape, slope, rough, crater_h, cats, args.site_km)
    hdr = ["site", "lon", "lat", "slope_med_deg", "slope_p95_deg", "rough_med_m",
           "rough_p95_m", "crater_haz_mean", "n_craters_in_window",
           "nearest_crater_km", "nearest_crater_diam_km"]
    print("  {:<16} {:>8} {:>7} {:>7} {:>7} {:>7} {:>8} {:>6} {:>7}".format(
        "site", "lon E", "sl med", "sl p95", "rg med", "rg p95", "crater",
        "n cr", "near km"))
    print("  {:<16} {:>8} {:>7} {:>7} {:>7} {:>7} {:>8} {:>6} {:>7}".format(
        "", "", "(deg)", "(deg)", "(m)", "(m)", "(0-1)", "", "(km)"))
    for r in rows:
        print("  {:<16} {:>8.3f} {:>7.2f} {:>7.2f} {:>7.2f} {:>7.2f} {:>8.3f} "
              "{:>6} {:>7.2f}".format(
                  r["site"], r["lon"], r["slope_med_deg"], r["slope_p95_deg"],
                  r["rough_med_m"], r["rough_p95_m"], r["crater_haz_mean"],
                  r["n_craters_in_window"], r["nearest_crater_km"]))
    with (OUT / "case_sites.csv").open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=hdr)
        wr.writeheader()
        wr.writerows(rows)

    ok = np.isfinite(p_safe) & (p_safe >= 0)
    robust_safe = ok & (p_safe >= 0.999)
    sensitive = ok & (p_safe > 0.1) & (p_safe < 0.9)
    never_safe = ok & (p_safe <= 0.001)
    print("")
    print("=== where the answer is parameter-dependent ===")
    print("  robustly safe      : {:>5.1f} % of the area".format(100 * robust_safe.mean()))
    print("  parameter-dependent: {:>5.1f} %".format(100 * sensitive.mean()))
    print("  never safe         : {:>5.1f} %".format(100 * never_safe.mean()))
    regs = []
    regs += region_table(sensitive, gt, px_m, slope, rough, args.top, "sensitive")
    regs += region_table(robust_safe, gt, px_m, slope, rough, args.top, "robust_safe")
    regs += region_table(never_safe, gt, px_m, slope, rough, args.top, "never_safe")
    print("")
    print("  {:<13} {:>10} {:>9} {:>8} {:>9} {:>9}".format(
        "kind", "area km2", "lon E", "lat N", "sl med", "rg med"))
    for r in regs:
        print("  {:<13} {:>10.1f} {:>9.4f} {:>8.4f} {:>9.2f} {:>9.2f}".format(
            r["kind"], r["area_km2"], r["lon"], r["lat"], r["slope_med_deg"],
            r["rough_med_m"]))
    if regs:
        with (OUT / "case_regions.csv").open("w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(regs[0].keys()))
            wr.writeheader()
            wr.writerows(regs)

    fig, ax = plt.subplots(1, 2, figsize=(15, 7))
    im = ax[0].imshow(score, cmap="RdYlGn_r", vmin=0, vmax=1)
    ax[0].set_title("suitability S (equal weights) with the named sites")
    fig.colorbar(im, ax=ax[0], fraction=0.046)
    for s in sites:
        r, c, _ = window_slice(gt, s["lon"], s["lat"], args.site_km, shape)
        if 0 <= r < shape[0] and 0 <= c < shape[1]:
            ax[0].scatter([c], [r], s=34, facecolors="none", edgecolors="blue")
            ax[0].annotate(s["label"], (c, r), fontsize=7, color="blue",
                           xytext=(4, -4), textcoords="offset points")
    im = ax[1].imshow(p_safe, cmap="viridis", vmin=0, vmax=1)
    ax[1].set_title("P(safe) over {} Monte Carlo draws".format(args.tag))
    fig.colorbar(im, ax=ax[1], fraction=0.046)
    for a in ax:
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT / "case_studies.png", dpi=140)
    print("")
    print("  wrote case_sites.csv, case_regions.csv, case_studies.png in outputs/week9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
