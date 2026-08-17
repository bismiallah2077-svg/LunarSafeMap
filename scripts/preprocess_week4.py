#!/usr/bin/env python3
"""Week 4: prepare the Rimae Bode study-area DEM from a SLDEM2015 tile.

Pipeline:
  1. Wrap the raw SLDEM FLOAT .IMG (km, float32, simple cylindrical)
     in a georeferenced VRT without copying the 1.3 GB tile.
  2. Crop to the study area bbox (default: 8-13 N, 353-359 E).
  3. Convert km -> m and write data/interim/week4/sldem_rimae_bode.tif.
  4. Print stats and write a small summary CSV.

Usage:
  python scripts/preprocess_week4.py [--bbox "353 8 359 13"]
"""
import argparse
import csv
from pathlib import Path

import numpy as np
from osgeo import gdal, osr

PPD = 512  # SLDEM2015 pixels per degree
RES_DEG = 1.0 / PPD
RADIUS_M = 1737_400.0


def build_vrt(img_path: Path, lbl_path: Path, vrt_path: Path) -> None:
    """Georeference the raw IMG via a VRT using projection params from the LBL."""
    text = lbl_path.read_text(encoding="utf-8", errors="replace")
    lines = int(_lbl(text, r"LINES\s*=\s*(\d+)"))
    samples = int(_lbl(text, r"LINE_SAMPLES\s*=\s*(\d+)"))
    west = float(_lbl(text, r"WESTERNMOST_LONGITUDE\s*=\s*([\d.]+)"))
    north = float(_lbl(text, r"MAXIMUM_LATITUDE\s*=\s*([\d.]+)"))

    # Pixel-registered: first pixel center is at (west, north).
    ulx = west - 0.5 * RES_DEG
    uly = north + 0.5 * RES_DEG

    srs = osr.SpatialReference()
    srs.ImportFromProj4(
        f"+proj=longlat +a={RADIUS_M} +b={RADIUS_M} +units=m +no_defs"
    )
    line_bytes = samples * 4  # float32
    vrt = f"""<VRTDataset rasterXSize="{samples}" rasterYSize="{lines}">
  <SRS>{srs.ExportToWkt()}</SRS>
  <GeoTransform>{ulx:.12f}, {RES_DEG:.12f}, 0.0, {uly:.12f}, 0.0, {-RES_DEG:.12f}</GeoTransform>
  <VRTRasterBand dataType="Float32" band="1" subClass="VRTRawRasterBand">
    <SourceFilename relativeToVRT="0">{img_path.as_posix()}</SourceFilename>
    <ImageOffset>0</ImageOffset>
    <PixelOffset>4</PixelOffset>
    <LineOffset>{line_bytes}</LineOffset>
    <ByteOrder>LSB</ByteOrder>
  </VRTRasterBand>
</VRTDataset>"""
    vrt_path.write_text(vrt, encoding="utf-8")


def _lbl(text: str, pattern: str) -> str:
    import re

    m = re.search(pattern, text, re.I)
    if not m:
        raise ValueError(f"field not found in LBL: {pattern}")
    return m.group(1).strip().strip('"\'')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--bbox",
        default="353 8 359 13",
        help="study area as 'lon_min lat_min lon_max lat_max' (degrees E, N)",
    )
    ap.add_argument(
        "--tile",
        default="SLDEM2015_512_00N_30N_315_360_FLOAT",
        help="SLDEM2015 tile stem (without extension)",
    )
    args = ap.parse_args()

    lon_min, lat_min, lon_max, lat_max = [float(v) for v in args.bbox.split()]

    repo = Path(__file__).resolve().parents[1]
    raw = repo / "data" / "raw" / "sldem2015"
    img = raw / f"{args.tile}.IMG"
    lbl = raw / f"{args.tile}.LBL"
    if not img.exists() or not lbl.exists():
        raise FileNotFoundError(
            f"tile not ready: {img} or {lbl} missing. Run scripts/download_sldem.sh first."
        )

    interim = repo / "data" / "interim" / "week4"
    outdir = repo / "outputs" / "week4"
    interim.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)

    # Allow the VRT to reference the raw IMG outside the VRT's directory.
    gdal.SetConfigOption(
        "GDAL_VRT_RAWRASTERBAND_ALLOWED_SOURCE",
        str((repo / "data").resolve()),
    )

    vrt = interim / f"{args.tile}.vrt"
    build_vrt(img, lbl, vrt)

    out_tif = interim / "sldem_rimae_bode_km.tif"
    gdal.Translate(
        str(out_tif),
        str(vrt),
        projWin=(lon_min, lat_max, lon_max, lat_min),
        format="GTiff",
        creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
    )

    # km -> m
    src = gdal.Open(str(out_tif))
    band = src.GetRasterBand(1)
    arr = band.ReadAsArray().astype("float32") * 1000.0
    gt = src.GetGeoTransform()
    wkt = src.GetProjection()
    cols, rows = src.RasterXSize, src.RasterYSize
    src = None

    out_m = interim / "sldem_rimae_bode.tif"
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(out_m), cols, rows, 1, gdal.GDT_Float32,
                    options=["COMPRESS=DEFLATE", "TILED=YES"])
    ds.SetGeoTransform(gt)
    ds.SetProjection(wkt)
    ds.GetRasterBand(1).WriteArray(arr)
    ds.GetRasterBand(1).ComputeStatistics(False)
    ds = None

    valid = arr[arr > -9000]
    stats = {
        "n_valid": int(valid.size),
        "min_m": float(valid.min()),
        "max_m": float(valid.max()),
        "mean_m": float(valid.mean()),
        "std_m": float(valid.std()),
        "p5_m": float(np.percentile(valid, 5)),
        "p95_m": float(np.percentile(valid, 95)),
    }
    with open(outdir / "sldem_study_area_stats.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats))
        w.writeheader()
        w.writerow(stats)

    print(f"study area DEM: {out_m}")
    print(f"size: {cols}x{rows} px, {RES_DEG*3600:.0f} arcsec/px")
    print(stats)
if __name__ == "__main__":
    main()
