#!/usr/bin/env python3
"""Week 6.6: list the false positives and the misses for manual inspection.

A detection-level precision of 0.451 only says "45 % of our detections match a
Robbins crater".  It cannot say whether the remaining 55 % are *wrong* or just
*missing from the catalogue* - that judgement needs a human looking at the
terrain.  This script produces the smallest possible set of things to look at:

  outputs/week6/review_false_positives.csv   every spurious detection
  outputs/week6/review_misses.csv            every known crater we missed
  outputs/week6/review_fp_map.png            quick-look over the study-area DEM

Usage
  python scripts/week6_review_false_positives.py               # everything
  python scripts/week6_review_false_positives.py --bin 1 2     # only 1-2 km
  python scripts/week6_review_false_positives.py --top 20      # 20 biggest only
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
from matplotlib.patches import Circle  # noqa: E402
from osgeo import gdal  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week6_mask_to_catalog as mtc  # noqa: E402

W6 = REPO / "outputs" / "week6"
STUDY_DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
MOON_M_PER_DEG = 30320.0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", nargs=2, type=float, metavar=("LO", "HI"),
                    help="only review detections in this diameter range (km)")
    ap.add_argument("--top", type=int, default=0,
                    help="only the N largest spurious detections")
    ap.add_argument("--mask", default=str(mtc.MASK),
                    help="predicted mask to review")
    args = ap.parse_args(argv[1:])

    mask, gt, ds = mtc.load_mask() if args.mask == str(mtc.MASK) else _load(args.mask)
    px_m = abs(gt[1]) * MOON_M_PER_DEG
    print("=== predicted mask: {} x {}, {:.2f} % coverage".format(
        mask.shape[1], mask.shape[0], 100.0 * mask.mean()))

    dets_raw, _ = mtc.components(mask, gt)
    dets = [d for d in dets_raw if d["diam_km"] >= mtc.MIN_DET_KM]
    gts = mtc.read_gt(mtc.GT)
    tp, fp, fn = mtc.match(dets, gts)
    print("  detections {:,} (>= {:.1f} km), truth {:,}, matched {:,}".format(
        len(dets), mtc.MIN_DET_KM, len(gts), len(tp)))

    if args.bin:
        lo, hi = args.bin
        fp = [d for d in fp if lo <= d["diam_km"] < hi]
        fn = [g for g in fn if lo <= g["diam_km"] < hi]
    fp = sorted(fp, key=lambda d: -d["area_px"])
    if args.top:
        fp = fp[: args.top]

    fp_path = W6 / "review_false_positives.csv"
    with fp_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "lon", "lat", "diam_km", "area_px",
                    "verdict", "note"])
        for i, d in enumerate(fp, 1):
            # verdict / note are left blank for the human reviewer
            w.writerow([i, round(d["lon"], 5), round(d["lat"], 5),
                        round(d["diam_km"], 3), d["area_px"], "", ""])
        print("  wrote {} ({:,} rows to review)".format(fp_path, len(fp)))

    fn_path = W6 / "review_misses.csv"
    with fn_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lon", "lat", "diam_km", "reason"])
        for g in sorted(fn, key=lambda g: -g["diam_km"]):
            w.writerow([round(g["lon"], 5), round(g["lat"], 5),
                        round(g["diam_km"], 3), ""])
        print("  wrote {} ({:,} rows to review)".format(fn_path, len(fn)))

    if STUDY_DEM.exists():
        dem_ds = gdal.Open(str(STUDY_DEM))
        z = dem_ds.GetRasterBand(1).ReadAsArray().astype("float32")
        dgt = dem_ds.GetGeoTransform()
        fig, ax = plt.subplots(figsize=(11, 9))
        ax.imshow(z, cmap="gray", origin="upper",
                  extent=(dgt[0], dgt[0] + dgt[1] * z.shape[1],
                          dgt[3] + dgt[5] * z.shape[0], dgt[3]))
        for g in gts:
            ax.add_patch(Circle((g["lon"], g["lat"]), g["diam_km"] / 111.0,
                                fill=False, ec="#39ff14", lw=0.7))
        if fp:
            ax.scatter([d["lon"] for d in fp], [d["lat"] for d in fp],
                       s=14, c="red", marker="x", label="spurious detection")
        ax.set_xlabel("longitude (deg E)")
        ax.set_ylabel("latitude (deg N)")
        ax.set_title("False positives to review (green = Robbins truth)")
        ax.legend(loc="upper right")
        fig.tight_layout()
        out_png = W6 / "review_fp_map.png"
        fig.savefig(out_png, dpi=150)
        print("  wrote {}".format(out_png))
    else:
        print("  (no study DEM at {} - skipped the quick-look map)".format(STUDY_DEM))
    return 0


def _load(path: str):
    ds = gdal.Open(path)
    if ds is None:
        raise SystemExit("cannot open {}".format(path))
    return (ds.GetRasterBand(1).ReadAsArray() > 0).astype(np.uint8), ds.GetGeoTransform(), ds


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
