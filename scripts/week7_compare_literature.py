#!/usr/bin/env python3
"""Week 7.5: do our suitable areas cover the candidate sites in the paper?

The four landing sites proposed by Yang et al. (2026, Fig. 5) are the only
independent reference we have for "where a landing site could be", so this is
the central validation of week 7:

  * what is the mean suitability S of a 5 km window centred on each LS?
  * where does that window rank among all windows in the study area?
  * is the point itself classified safe / caution / danger?
  * how far is it from our own best candidate site?

The window definition is imported from week7_suitability, so "the suitability
of a site" means exactly the same thing here as in the ranking.

Usage
  python scripts/week7_compare_literature.py --selftest
  python scripts/week7_compare_literature.py --tag equal
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week7_suitability as w7  # noqa: E402

OUT = REPO / "outputs" / "week7"
SITES_FILE = REPO / "configs" / "landing_sites.csv"
CLASS_NAME = {1: "safe", 2: "caution", 3: "danger"}
MOON_M_PER_DEG = 30320.0


def read_sites(path):
    out = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(r for r in f if not r.startswith("#")):
            if not row.get("lon") or not row.get("lat"):
                continue
            out.append({"label": row["label"].strip(),
                        "lon": float(row["lon"]), "lat": float(row["lat"])})
    return out


def read_raster(path):
    ds = gdal.Open(str(path))
    if ds is None:
        raise SystemExit("cannot open {}".format(path))
    band = ds.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    a = band.ReadAsArray()
    if nodata is not None:
        a = np.where(a == nodata, np.nan, a)
    return a.astype("float32"), ds.GetGeoTransform()


def to_pixel(gt, lon, lat):
    """(lon, lat) -> (row, col) as integers, or None when outside the raster."""
    col = int(round((lon - gt[0]) / gt[1] - 0.5))
    row = int(round((lat - gt[3]) / gt[5] - 0.5))
    return row, col


def distance_km(a_lon, a_lat, b_lon, b_lat):
    """Local equirectangular distance - fine at the scale of one study area."""
    dlat = (b_lat - a_lat) * MOON_M_PER_DEG / 1000.0
    dlon = (b_lon - a_lon) * MOON_M_PER_DEG / 1000.0 * math.cos(
        math.radians(0.5 * (a_lat + b_lat)))
    return math.hypot(dlat, dlon)


def rank_field(mean):
    """Rank of every valid window, 1 = the lowest (best) mean S.

    One scatter assignment only: out_flat[order[k]] = k + 1.  An earlier version
    went through an intermediate array indexed by flat pixel id, which built a
    shifted mapping (the small self test passed by luck, the real 7.9 million
    pixel field did not) - hence the brute force cross-check in the self test.
    """
    out = np.full(mean.shape, np.nan)
    flat = np.flatnonzero(np.isfinite(mean))
    order = flat[np.argsort(mean.ravel()[flat], kind="stable")]
    out.ravel()[order] = np.arange(1, order.size + 1, dtype="float64")
    return out, order.size


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
    r, c = to_pixel(gt, 355.76, 11.43)
    lon = gt[0] + gt[1] * (c + 0.5)
    lat = gt[3] + gt[5] * (r + 0.5)
    check("pixel round trip in longitude", lon, 355.76, 0.002)
    check("pixel round trip in latitude", lat, 11.43, 0.002)

    const = np.full((40, 40), 0.25, dtype="float32")
    classes = np.ones((40, 40), dtype="uint8")
    mean, danger = w7.window_stats_field(const, classes, 5)
    check("constant field -> same window mean", np.nanmean(mean), 0.25)
    check("constant field -> zero danger", np.nanmean(danger), 0.0)

    ramp = np.zeros((60, 60), dtype="float32")
    ramp[:, :] = np.linspace(0, 1, 60)[None, :]
    m2, _ = w7.window_stats_field(ramp, np.ones((60, 60), dtype="uint8"), 5)
    ranks, n = rank_field(m2)
    check("rank of the best window is 1", np.nanmin(ranks), 1.0)
    check("rank of the worst window is n", np.nanmax(ranks), float(n))
    check("the best window sits at the low-value edge",
          float(np.nanmin(np.where(ranks == 1, ramp, np.nan))), 0.0, 0.02)

    # brute force cross-check: rank = 1 + number of windows with a smaller mean
    rng = np.random.default_rng(0)
    rnd = rng.random((25, 30)).astype("float32")
    rnd[3, 4] = np.nan
    rk, n_r = rank_field(rnd)
    vals = rnd[np.isfinite(rnd)]
    worst = 0
    for r in range(rnd.shape[0]):
        for c in range(rnd.shape[1]):
            if not np.isfinite(rnd[r, c]):
                continue
            want = int((vals < rnd[r, c]).sum()) + 1
            worst = max(worst, abs(int(rk[r, c]) - want))
    check("rank agrees with the brute force count (max error)", worst, 0)
    check("nodata stays NaN", float(np.isnan(rk[3, 4])), 1.0)

    check("1 deg of latitude on the Moon", distance_km(0.0, 0.0, 0.0, 1.0), 30.32, 0.01)
    check("distance is symmetric",
          distance_km(355.0, 10.0, 356.0, 11.0),
          distance_km(356.0, 11.0, 355.0, 10.0))

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tag", default="equal", help="which suitability run to compare")
    ap.add_argument("--site-km", type=float, default=5.0)
    ap.add_argument("--sites-file", default=str(SITES_FILE))
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        return selftest()

    score, gt = read_raster(OUT / "suitability_{}.tif".format(args.tag))
    classes, _ = read_raster(OUT / "suitability_classes_{}.tif".format(args.tag))
    classes = np.nan_to_num(classes).astype("uint8")
    px_m = abs(gt[1]) * MOON_M_PER_DEG
    win = max(3, int(round(args.site_km * 1000.0 / px_m)))
    mean, danger = w7.window_stats_field(score, classes, win)
    ranks, n_windows = rank_field(mean)
    print("=== suitability run: {} ===".format(args.tag))
    print("  {} x {}, {:.2f} m/px, site window {} px ({:.1f} km), "
          "{:,} valid windows".format(score.shape[1], score.shape[0], px_m, win,
                                      args.site_km, n_windows))

    cand_path = OUT / "candidate_sites_{}.csv".format(args.tag)
    candidates = []
    if cand_path.exists():
        with cand_path.open(newline="", encoding="utf-8-sig") as f:
            candidates = list(csv.DictReader(f))

    sites = read_sites(Path(args.sites_file))
    rows = []
    print("")
    print("  {:>14} {:>9} {:>8} {:>8} {:>9} {:>9} {:>9}".format(
        "label", "lon E", "mean S", "danger%", "rank", "of", "nearest"))
    for s in sites:
        r, c = to_pixel(gt, s["lon"], s["lat"])
        if not (0 <= r < score.shape[0] and 0 <= c < score.shape[1]):
            print("  {:>14}  outside the study area".format(s["label"]))
            continue
        m = float(mean[r, c]) if np.isfinite(mean[r, c]) else float("nan")
        d = float(danger[r, c]) if np.isfinite(danger[r, c]) else float("nan")
        rk = int(ranks[r, c]) if np.isfinite(ranks[r, c]) else -1
        near = None
        if candidates:
            near = min(candidates, key=lambda k: distance_km(
                s["lon"], s["lat"], float(k["lon"]), float(k["lat"])))
        dist = (distance_km(s["lon"], s["lat"], float(near["lon"]),
                            float(near["lat"])) if near else float("nan"))
        cls = CLASS_NAME.get(int(classes[r, c]), "?")
        # percentage of windows that are *better* than this one (higher = better)
        pct = 100.0 * (n_windows - rk) / n_windows if rk > 0 else float("nan")
        rows.append({"label": s["label"], "lon": s["lon"], "lat": s["lat"],
                     "mean_S": round(m, 4), "danger_pct": round(100 * max(d, 0), 2),
                     "window_rank": rk, "n_windows": n_windows,
                     "rank_pct": round(pct, 1), "class_at_point": cls,
                     "nearest_candidate_km": round(dist, 2) if near else ""})
        print("  {:>14} {:>9.4f} {:>8.3f} {:>8.2f} {:>6}/{:>5} {:>8.1f}% {:>9}".format(
            s["label"], s["lon"], m, 100 * max(d, 0.0), rk, n_windows, pct,
            "{:.1f} km".format(dist) if near else "-"))

    out_csv = OUT / "literature_comparison_{}.csv".format(args.tag)
    with out_csv.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print("")
    print("  wrote {}".format(out_csv))
    paper_best = min(rows, key=lambda x: x["mean_S"]) if rows else None
    if paper_best:
        print("  best of the paper's sites: {} (mean S {:.3f}, rank {:,}/{:,}, {})".format(
            paper_best["label"], paper_best["mean_S"], paper_best["window_rank"],
            paper_best["n_windows"], paper_best["class_at_point"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
