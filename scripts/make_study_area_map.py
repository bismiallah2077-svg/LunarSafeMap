#!/usr/bin/env python3
"""Week 4: produce the Rimae Bode study-area base map.

Uses the SLDEM2015 crop prepared by preprocess_week4.py:
  - hillshade basemap
  - elevation as semi-transparent color layer
  - study-area bounding box
  - optional candidate landing points (configs/landing_sites.csv)

Outputs: outputs/week4/study_area_map.png (+ .csv of pixel stats)
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from osgeo import gdal

REPO = Path(__file__).resolve().parents[1]
DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
OUT = REPO / "outputs" / "week4"
SITES = REPO / "configs" / "landing_sites.csv"


def main() -> None:
    if not DEM.exists():
        raise FileNotFoundError(f"run scripts/preprocess_week4.py first: {DEM}")

    ds = gdal.Open(str(DEM))
    band = ds.GetRasterBand(1)
    elev = band.ReadAsArray().astype("float32")
    gt = ds.GetGeoTransform()
    wkt = ds.GetProjection()
    ds = None

    OUT.mkdir(parents=True, exist_ok=True)

    # hillshade
    hs_tif = OUT / "hillshade.tif"
    gdal.DEMProcessing(
        str(hs_tif), str(DEM), "hillshade",
        azimuth=315, altitude=45, zFactor=1.0,
        creationOptions=["COMPRESS=DEFLATE"],
    )
    hds = gdal.Open(str(hs_tif))
    shade = hds.GetRasterBand(1).ReadAsArray().astype("float32")
    hds = None

    x0, dx, _, y0, _, dy = gt
    extent = [x0, x0 + elev.shape[1] * dx, y0 + elev.shape[0] * dy, y0]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(shade, cmap="gray", extent=extent, aspect="auto", vmin=0, vmax=255)
    im = ax.imshow(
        elev,
        cmap="terrain",
        extent=extent,
        aspect="auto",
        alpha=0.55,
        vmin=-4500,
        vmax=2500,
    )
    plt.colorbar(im, ax=ax, label="Elevation (m, SLDEM2015)", shrink=0.85)

    ax.set_xlim(353.0, 359.0)
    ax.set_ylim(8.0, 13.0)
    ax.set_xlabel("East longitude (°)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("Rimae Bode study area — SLDEM2015 (512 ppd, ~60 m/px)")

    # candidate landing sites (if provided)
    if SITES.exists():
        rows = [
            line for line in SITES.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if len(rows) > 1:
            for row in csv.DictReader(rows):
                if not row.get("lon", "").strip() or not row.get("lat", "").strip():
                    continue  # placeholder row, coordinates not filled in yet
                ax.plot(
                    float(row["lon"]),
                    float(row["lat"]),
                    "r*", ms=14, mec="k", mew=0.6,
                    label=row.get("label", ""),
                )
        if ax.get_legend_handles_labels()[1]:
            ax.legend(loc="lower right", fontsize=8)

    ax.add_patch(Rectangle(
        (353.0, 8.0), 6.0, 5.0,
        fill=False, edgecolor="crimson", lw=1.6,
    ))
    ax.grid(True, ls=":", lw=0.4, alpha=0.5)

    fig.tight_layout()
    fig.savefig(OUT / "study_area_map.png", dpi=160)
    print(f"wrote {OUT / 'study_area_map.png'}")

    # pixel stats table for the report
    valid = elev[elev > -9000]
    with (OUT / "study_area_elevation_stats.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["n_px", valid.size])
        w.writerow(["min_m", round(float(valid.min()), 2)])
        w.writerow(["max_m", round(float(valid.max()), 2)])
        w.writerow(["mean_m", round(float(valid.mean()), 2)])
        w.writerow(["std_m", round(float(valid.std()), 2)])
    print(f"wrote {OUT / 'study_area_elevation_stats.csv'}")


if __name__ == "__main__":
    main()
