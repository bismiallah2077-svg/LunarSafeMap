#!/usr/bin/env python3
"""Week 6.0 (teaching tool): look at a training sample with your own eyes.

A "sample" in this project is nothing more exotic than
  input : a 256 x 256 window of elevation values (a numpy array)
  label : a 256 x 256 map of 0/1 (1 = inside a Robbins crater disc)

Before trusting any metric, print the numbers and look at the picture.
This script picks three contrasting tiles from the study area, prints their
statistics and writes outputs/week6/sample_tiles.png with one row per tile:
DEM | label | model prediction.

Usage
  python scripts/week6_show_sample.py
  python scripts/week6_show_sample.py --size 128 --out /tmp/x.png
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

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
W6 = REPO / "outputs" / "week6"
INTERIM = REPO / "data" / "interim" / "week6"
DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
LABEL = INTERIM / "crater_mask_sldem.tif"
PRED = W6 / "study_area_crater_pred.tif"


def read_tiles(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def pick(tiles):
    """Three contrasting tiles: crowded, one crater, empty."""
    crowded = max(tiles, key=lambda t: int(t["crater_centres"]))
    one = next((t for t in tiles if int(t["crater_centres"]) == 1), None)
    empty = next((t for t in tiles if int(t["crater_centres"]) == 0), None)
    out = [("crowded ({} crater centres)".format(crowded["crater_centres"]), crowded)]
    if one:
        out.append(("one crater", one))
    if empty:
        out.append(("no crater (negative sample)", empty))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", default=str(INTERIM / "tiles.csv"))
    ap.add_argument("--out", default=str(W6 / "sample_tiles.png"))
    ap.add_argument("--size", type=int, default=256)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    for p in (DEM, LABEL, PRED):
        if not p.exists():
            raise SystemExit("missing {} - run the week-6 pipeline first".format(p))

    dem_ds, lab_ds, pred_ds = gdal.Open(str(DEM)), gdal.Open(str(LABEL)), gdal.Open(str(PRED))
    rows = pick(read_tiles(Path(args.tiles)))
    n = args.size

    fig, axes = plt.subplots(len(rows), 3, figsize=(10.5, 3.4 * len(rows)), squeeze=False)
    for i, (name, t) in enumerate(rows):
        r0, c0 = int(t["row0"]), int(t["col0"])
        dem = dem_ds.ReadAsArray(c0, r0, n, n).astype("float32")
        lab = lab_ds.ReadAsArray(c0, r0, n, n)
        prd = pred_ds.ReadAsArray(c0, r0, n, n)
        frac = float((lab > 0).mean())
        frac_p = float((prd > 0).mean())

        print("=== {} ===".format(name))
        print("  tile {}  rows {}..{}  cols {}..{}".format(
            t["tile_id"], r0, r0 + n, c0, c0 + n))
        print("  lon {:.3f}-{:.3f} E   lat {:.3f}-{:.3f} N".format(
            float(t["lon_min"]), float(t["lon_max"]),
            float(t["lat_min"]), float(t["lat_max"])))
        print("  input  : shape {}, elevation {:.0f} .. {:.0f} m (median {:.0f} m)".format(
            dem.shape, float(np.nanmin(dem)), float(np.nanmax(dem)),
            float(np.nanmedian(dem))))
        print("  label  : {:.2f} % of the {} pixels are crater ({:,} px)".format(
            100.0 * frac, n * n, int((lab > 0).sum())))
        print("  predict: {:.2f} % of the pixels are predicted crater".format(100.0 * frac_p))
        if i == 0:
            print("  the same input as an 8x8 table of block means (metres):")
            b = n // 8
            blocks = dem[:8 * b, :8 * b].reshape(8, b, 8, b).mean(axis=(1, 3))
            for r in blocks:
                print("    " + " ".join("{:7.1f}".format(v) for v in r))
        print("")

        ax = axes[i][0]
        im = ax.imshow(dem, cmap="terrain")
        ax.set_title("{}: input DEM".format(name), fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.046, label="m")
        ax = axes[i][1]
        ax.imshow(lab, cmap="gray", vmin=0, vmax=1)
        ax.set_title("label (truth): {:.1f} % crater".format(100.0 * frac), fontsize=10)
        ax = axes[i][2]
        ax.imshow(prd, cmap="gray", vmin=0, vmax=1)
        ax.set_title("model prediction: {:.1f} %".format(100.0 * frac_p), fontsize=10)
        for a in axes[i]:
            a.set_xticks([])
            a.set_yticks([])

    fig.tight_layout()
    out = Path(args.out)
    fig.savefig(out, dpi=140)
    print("wrote {}".format(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
