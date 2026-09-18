#!/usr/bin/env python3
"""Re-assign a lunar CRS to the WMS-sourced WAC GeoTIFF.

The USGS Moon WMS returns GeoTIFF tagged as EPSG:4326 (Earth), but the
coordinates are selenographic lon/lat degrees. This script rewrites the CRS
to a lunar sphere (R = 1737.4 km) so the WAC image overlays SLDEM exactly.

Usage: python scripts/preprocess_wac.py
"""
from pathlib import Path

from osgeo import gdal, osr

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "wac"
OUT = REPO / "data" / "interim" / "week4"


def main() -> None:
    tiles = sorted(RAW.glob("*.tif"))
    if not tiles:
        raise FileNotFoundError(f"no WAC GeoTIFF in {RAW}; run scripts/download_wac.py")
    OUT.mkdir(parents=True, exist_ok=True)

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat +a=1737400 +b=1737400 +units=m +no_defs")
    wkt = srs.ExportToWkt()

    for tif in tiles:
        dst = OUT / "wac_rimae_bode.tif"
        gdal.Translate(
            str(dst), str(tif),
            outputSRS=wkt,
            format="GTiff",
            creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
        )
        ds = gdal.Open(str(dst))
        gt = ds.GetGeoTransform()
        print(f"{tif.name} -> {dst.name}")
        print(f"  size {ds.RasterXSize} x {ds.RasterYSize}, bands {ds.RasterCount}")
        print(f"  origin ({gt[0]:.6f}, {gt[3]:.6f}), pixel ({gt[1]:.8f}, {gt[5]:.8f})")
        print("  CRS: lunar sphere R=1737.4 km")
        ds = None


if __name__ == "__main__":
    main()