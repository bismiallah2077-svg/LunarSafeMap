#!/usr/bin/env python3
"""Week 11: which candidate sites could ever be checked at metre scale?

The metre-scale validation of H1 needs a NAC stereo DEM, and NAC stereo coverage
is rare: a pair requires a deliberate slew on a later orbit, so a given point
usually has only one pass (see docs/nac_stereo_search_2026-09-19.md).  Our own
NAC strip covers about 1 % of the study area and overlaps none of the top ten
sites, so the question that actually decides the H1 plan is:

    **If a candidate site has to lie inside the existing NAC coverage, which one
    wins, and how much suitability do we give up by requiring that?**

This script answers it on the existing products (no new downloads): it masks the
5 km windows to the NAC footprint, ranks the sites again, and compares the
result with the unrestricted ranking.

Outputs: outputs/week11/nac_footprint_sites.csv, nac_footprint_sites.png

Usage
  python scripts/week11_nac_footprint_sites.py --selftest
  python scripts/week11_nac_footprint_sites.py --tag equal --min-inside 0.95
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
from scipy import ndimage  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week5_terrain_metrics as w5  # noqa: E402
import week7_suitability as w7  # noqa: E402
import week7_compare_literature as w7c  # noqa: E402

OUT = REPO / "outputs" / "week11"
W7 = REPO / "outputs" / "week7"
STUDY_DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
NAC_DEM = REPO / "outputs" / "week4" / "nac_dem.tif"
MOON_M_PER_DEG = 30320.0
SITE_KM = 5.0


def rank_within(mask_ok, score, mean, win, top_n):
    """Greedy non-overlapping ranking of the windows that satisfy mask_ok."""
    order = np.argsort(np.where(mask_ok, mean, np.inf).ravel())
    taken = np.zeros(mean.shape, dtype=bool)
    sites = []
    ny, nx = mean.shape
    for idx in order:
        r, c = divmod(int(idx), nx)
        if not mask_ok[r, c]:
            break
        if taken[r, c]:
            continue
        sites.append((r, c, float(mean[r, c])))
        r0, r1 = max(0, r - win), min(ny, r + win + 1)
        c0, c1 = max(0, c - win), min(nx, c + win + 1)
        taken[r0:r1, c0:c1] = True
        if len(sites) >= top_n:
            break
    return sites


def selftest():
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:56s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    mean = np.full((40, 40), 0.5)
    mean[3, 3] = 0.01          # global best, outside the mask
    mean[30, 30] = 0.20        # best inside the mask
    ok = np.zeros((40, 40), dtype=bool)
    ok[20:40, 20:40] = True
    sites = rank_within(ok, mean, mean, 3, 3)
    check("ranking ignores the better window outside the footprint",
          float(sites[0][2]), 0.20, 1e-9)
    check("the chosen window is inside the footprint",
          float(ok[sites[0][0], sites[0][1]]), 1.0)
    check("no overlap between the chosen windows",
          float(abs(sites[0][0] - sites[1][0]) >= 3 or abs(sites[0][1] - sites[1][1]) >= 3),
          1.0)
    all_sites = rank_within(np.ones_like(ok), mean, mean, 3, 1)
    check("without the mask the global best is returned",
          float(all_sites[0][2]), 0.01, 1e-9)

    check("an 84 px window is about 5 km wide",
          84 * 59.22 / 1000.0, 5.0, 0.1)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tag", default="equal")
    ap.add_argument("--site-km", type=float, default=SITE_KM)
    ap.add_argument("--min-inside", type=float, default=0.95,
                    help="minimum fraction of the window that must lie inside the NAC footprint")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        return selftest()

    OUT.mkdir(parents=True, exist_ok=True)
    score, gt = w7c.read_raster(W7 / ("suitability_" + args.tag + ".tif"))
    classes, _ = w7c.read_raster(W7 / ("suitability_classes_" + args.tag + ".tif"))
    classes = np.nan_to_num(classes).astype("uint8")
    px_m = abs(gt[1]) * MOON_M_PER_DEG
    win = max(3, int(round(args.site_km * 1000.0 / px_m)))

    footprint = w5.nac_footprint_on(STUDY_DEM, NAC_DEM).astype("float64")
    if footprint.shape != score.shape:
        raise SystemExit("the footprint mask is not on the suitability grid")
    # fraction of each window that lies inside the NAC footprint (1.0 = fully inside)
    frac_inside = ndimage.uniform_filter(footprint, size=win)
    ok = np.isfinite(frac_inside) & (frac_inside >= args.min_inside)
    mean, danger = w7.window_stats_field(score, classes, win)
    print("=== inputs ===")
    print("  NAC footprint covers {:.2f} % of the study area".format(
        100.0 * float(footprint.mean())))
    print("  windows fully inside the footprint ({:.0f} % threshold): {:,} of {:,}".format(
        100 * args.min_inside, int(ok.sum()), int(np.isfinite(mean).sum())))

    sites = rank_within(ok, score, mean, win, args.top)
    if not sites:
        print("  no 5 km window lies inside the NAC footprint")
        return 0
    rows = []
    for i, (r, c, m) in enumerate(sites, 1):
        lon = gt[0] + gt[1] * (c + 0.5)
        lat = gt[3] + gt[5] * (r + 0.5)
        rows.append({"rank": i, "lon": round(float(lon), 4), "lat": round(float(lat), 4),
                     "mean_S": round(m, 4),
                     "danger_pct": round(100 * max(0.0, float(danger[r, c])), 2)})
    global_best = None
    gp = W7 / "candidate_sites_{}.csv".format(args.tag)
    if gp.exists():
        with gp.open(newline="", encoding="utf-8-sig") as f:
            first = next(csv.DictReader(f))
            global_best = (float(first["lon"]), float(first["lat"]), float(first["mean_S"]))

    print("")
    print("=== best sites inside the NAC footprint ===")
    print("  {:>4} {:>10} {:>10} {:>9} {:>9}".format("rank", "lon E", "lat N", "mean S", "danger %"))
    for r in rows:
        print("  {:>4} {:>10.4f} {:>10.4f} {:>9.4f} {:>9.2f}".format(
            r["rank"], r["lon"], r["lat"], r["mean_S"], r["danger_pct"]))
    if global_best:
        d = math.hypot((rows[0]["lat"] - global_best[1]) * MOON_M_PER_DEG / 1000.0,
                       (rows[0]["lon"] - global_best[0]) * MOON_M_PER_DEG / 1000.0
                       * math.cos(math.radians(global_best[1])))
        print("")
        print("  unrestricted best : {:.4f} E {:.4f} N  mean S {:.4f}".format(*global_best))
        print("  best inside NAC   : {:.4f} E {:.4f} N  mean S {:.4f}".format(
            rows[0]["lon"], rows[0]["lat"], rows[0]["mean_S"]))
        print("  they are {:.1f} km apart; suitability penalty {:.3f}".format(
            d, rows[0]["mean_S"] - global_best[2]))
    with (OUT / "nac_footprint_sites.csv").open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    fig, ax = plt.subplots(1, 2, figsize=(14, 7))
    im = ax[0].imshow(score, cmap="RdYlGn_r", vmin=0, vmax=1)
    ax[0].contour(footprint > 0.5, levels=[0.5], colors="cyan", linewidths=1.5)
    for r in rows:
        c = int(round((r["lon"] - gt[0]) / gt[1] - 0.5))
        rr = int(round((r["lat"] - gt[3]) / gt[5] - 0.5))
        ax[0].scatter([c], [rr], s=46, facecolors="none", edgecolors="blue")
        ax[0].annotate(str(r["rank"]), (c, rr), fontsize=8, color="blue",
                       xytext=(4, -4), textcoords="offset points")
    ax[0].set_title("suitability (equal weights)\ncyan outline = NAC stereo footprint")
    fig.colorbar(im, ax=ax[0], fraction=0.046)
    ax[1].imshow(footprint, cmap="Blues", vmin=0, vmax=1)
    ax[1].set_title("NAC coverage mask ({:.2f} % of the study area)".format(
        100 * float(footprint.mean())))
    for a in ax:
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT / "nac_footprint_sites.png", dpi=140)
    print("")
    print("  wrote nac_footprint_sites.csv and nac_footprint_sites.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
