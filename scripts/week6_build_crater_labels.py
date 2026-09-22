#!/usr/bin/env python3
"""Week 6.1: build a crater detection dataset from the Robbins (2018) catalog.

Pipeline:
  1. download the Robbins 2018 bundle from the USGS Astrogeology CKAN
     (verified URL, 91.8 MB zip);
  2. read the crater catalogue and locate the latitude / longitude / diameter
     columns by name (the header is printed, so a format change is visible);
  3. subset to the study area and, separately, to a surrounding training
     region so training and test tiles can be split *geographically*;
  4. rasterise the craters as filled discs onto the study-area DEM grid and
     build a tile index with the crater count per tile.

Outputs (data/interim/week6/):
  craters_study_area.csv, craters_training_region.csv,
  crater_mask_sldem.tif, tiles.csv
"""
import csv
import io
import math
import os
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "robbins"
OUT = REPO / "data" / "interim" / "week6"
DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"

URL = ("https://astrogeology.usgs.gov/ckan/dataset/"
       "f89f5478-b69a-486c-b9b5-30d7b0c5ad2b/resource/"
       "c4f25cc2-4f8a-4207-a845-5e176da3ac5a/download/"
       "lunar_crater_database_robbins_2018")
ZIP_NAME = "lunar_crater_database_robbins_2018.zip"
EXPECTED_ZIP_BYTES = 96_227_201          # exact size, verified against the server

STUDY = (353.0, 8.0, 359.0, 13.0)          # west, south, east, north
TRAIN = (340.0, 0.0, 360.0, 20.0)          # broader surrounding region
MOON_M_PER_DEG = 30320.0
TILE_PX = 256
MIN_DIAM_KM = 1.0                          # Robbins >= 1 km is the reliable part


def download(url, dest, expected_bytes):
    """Resumable, retrying download; returns only once the full size is reached."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    attempt = 0
    while True:
        have = dest.stat().st_size if dest.exists() else 0
        if have == expected_bytes:
            print("  complete: {:,} bytes".format(have))
            return dest
        attempt += 1
        req = urllib.request.Request(url, headers={"User-Agent": "LunarSafeMap/0.1"})
        if have:
            req.add_header("Range", "bytes={}-".format(have))
        try:
            with urllib.request.urlopen(req, timeout=180) as r, \
                    open(dest, "ab" if have else "wb") as f:
                if have and getattr(r, "status", 0) == 200:
                    f.truncate(0)              # server ignored Range: restart clean
                while True:
                    block = r.read(1 << 20)
                    if not block:
                        break
                    f.write(block)
        except Exception as e:
            print("  attempt {} failed: {} (have {:,} bytes)".format(
                attempt, e, dest.stat().st_size))
        now = dest.stat().st_size
        print("  have {:,} / {:,} bytes".format(now, expected_bytes))
        if now >= expected_bytes:
            print("  complete: {:,} bytes".format(now))
            return dest
        if attempt >= 40:
            raise SystemExit("download incomplete after {} attempts".format(attempt))
        time.sleep(4)


def find_columns(header):
    """Locate latitude / longitude / diameter columns by name."""
    low = [h.strip().lower() for h in header]
    def pick(*cands):
        for c in cands:
            for i, h in enumerate(low):
                if h == c:
                    return i
        for c in cands:
            for i, h in enumerate(low):
                if c in h:
                    return i
        return None
    return pick("latitude", "lat"), pick("longitude", "lon"), \
        pick("diameter", "diam")


def read_catalog(path):
    """Return (rows, header) where rows are (lat, lon, diam_km)."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader)
        ilat, ilon, idiam = find_columns(header)
        if ilat is None or ilon is None or idiam is None:
            raise SystemExit("could not find lat/lon/diameter in: {}".format(header))
        rows = []
        for r in reader:
            try:
                rows.append((float(r[ilat]), float(r[ilon]), float(r[idiam])))
            except (ValueError, IndexError):
                continue
    return rows, header


def in_box(lat, lon, box):
    w, s, e, n = box
    if not (s <= lat <= n):
        return False
    if w <= e:
        return w <= lon <= e
    return lon >= w or lon <= e          # box crossing 0/360


def subset(rows, box, min_diam=MIN_DIAM_KM):
    return [r for r in rows if r[2] >= min_diam and in_box(r[0], r[1], box)]


def crater_disc_mask(shape, gt, craters):
    """Rasterise craters as filled discs on a lon/lat grid.

    shape : (rows, cols); gt : (x0, dx, 0, y0, 0, dy) in degrees.
    Returns a uint8 array (1 inside a crater).
    """
    mask = np.zeros(shape, dtype=np.uint8)
    ny, nx = shape
    x0, dx, _, y0, _, dy = gt
    for lat, lon, diam_km in craters:
        dlat = (diam_km / 2.0) * 1000.0 / MOON_M_PER_DEG   # km -> m -> degrees
        dlon = dlat / max(math.cos(math.radians(lat)), 1e-6)
        # pixel index of a coordinate: r = (lat - y0) / dy - 0.5
        r1 = (lat + dlat - y0) / dy - 0.5
        r2 = (lat - dlat - y0) / dy - 0.5
        c1 = (lon - dlon - x0) / dx - 0.5
        c2 = (lon + dlon - x0) / dx - 0.5
        row_lo = max(0, int(math.floor(min(r1, r2))))
        row_hi = min(ny, int(math.ceil(max(r1, r2))) + 1)
        col_lo = max(0, int(math.floor(min(c1, c2))))
        col_hi = min(nx, int(math.ceil(max(c1, c2))) + 1)
        if row_hi <= row_lo or col_hi <= col_lo:
            continue
        rr = y0 + dy * (np.arange(row_lo, row_hi) + 0.5)
        cc = x0 + dx * (np.arange(col_lo, col_hi) + 0.5)
        dlat_grid = (rr[:, None] - lat) / dlat
        dlon_grid = (cc[None, :] - lon) / dlon
        inside = (dlat_grid ** 2 + dlon_grid ** 2) <= 1.0
        mask[row_lo:row_hi, col_lo:col_hi] |= inside.astype(np.uint8)
    return mask


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    print("=== 1. Robbins 2018 catalogue ===")
    zpath = RAW / ZIP_NAME
    download(URL, zpath, EXPECTED_ZIP_BYTES)
    print("  zip size: {:,} bytes".format(zpath.stat().st_size))

    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        print("  csv members: {}".format(names[:5]))
        if not names:
            raise SystemExit("no csv inside the archive")
        csv_name = max(names, key=lambda n: z.getinfo(n).file_size)
        print("  using {} ({:,} bytes)".format(csv_name,
                                               z.getinfo(csv_name).file_size))
        with z.open(csv_name) as fh:
            data = fh.read().decode("utf-8", errors="replace")
    tmp_csv = OUT / "robbins_raw.csv"
    tmp_csv.write_text(data, encoding="utf-8")
    rows, header = read_catalog(tmp_csv)
    print("  catalogue rows: {:,}".format(len(rows)))
    print("  header (first 6): {}".format(header[:6]))

    print("")
    print("=== 2. subsets ===")
    study = subset(rows, STUDY, min_diam=0.0)
    train = subset(rows, TRAIN, min_diam=MIN_DIAM_KM)
    print("  study area  {}-{}E {}-{}N : {:,} craters (all sizes, >= {:.1f} km in tiles)"
          .format(STUDY[0], STUDY[2], STUDY[1], STUDY[3], len(study), MIN_DIAM_KM))
    if study:
        d = np.array([r[2] for r in study])
        print("    diameter: median {:.2f} km, p90 {:.2f} km, max {:.2f} km"
              .format(float(np.median(d)), float(np.percentile(d, 90)), float(d.max())))
    print("  training region {}-{}E {}-{}N : {:,} craters >= {:.1f} km"
          .format(TRAIN[0], TRAIN[2], TRAIN[1], TRAIN[3], len(train), MIN_DIAM_KM))

    with (OUT / "craters_study_area.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lat", "lon", "diameter_km"])
        w.writerows(study)
    with (OUT / "craters_training_region.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lat", "lon", "diameter_km"])
        w.writerows(train)

    print("")
    print("=== 3. rasterise labels on the study-area DEM grid ===")
    ds = gdal.Open(str(DEM))
    gt = ds.GetGeoTransform()
    shape = (ds.RasterYSize, ds.RasterXSize)
    print("  grid {} x {}, pixel {:.6f} deg".format(shape[1], shape[0], abs(gt[1])))
    discs = [r for r in study if r[2] >= MIN_DIAM_KM]
    mask = crater_disc_mask(shape, gt, discs)
    print("  craters used: {:,}; mask area {:,} px ({:.2f} % of the scene)"
          .format(len(discs), int(mask.sum()), 100.0 * mask.mean()))
    drv = gdal.GetDriverByName("GTiff")
    mpath = OUT / "crater_mask_sldem.tif"
    mds = drv.Create(str(mpath), shape[1], shape[0], 1, gdal.GDT_Byte,
                     options=["COMPRESS=DEFLATE"])
    mds.SetGeoTransform(gt)
    mds.SetProjection(ds.GetProjection())
    mds.GetRasterBand(1).WriteArray(mask)
    mds = None
    print("  wrote {}".format(mpath))

    print("")
    print("=== 4. tile index ===")
    nty = shape[0] // TILE_PX
    ntx = shape[1] // TILE_PX
    rows_out = []
    for ty in range(nty):
        for tx in range(ntx):
            r0, c0 = ty * TILE_PX, tx * TILE_PX
            sub = mask[r0:r0 + TILE_PX, c0:c0 + TILE_PX]
            lon_min = gt[0] + c0 * gt[1]
            lon_max = gt[0] + (c0 + TILE_PX) * gt[1]
            lat_max = gt[3] + r0 * gt[5]
            lat_min = gt[3] + (r0 + TILE_PX) * gt[5]
            ncr = sum(1 for lat, lon, dm in discs
                      if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max)
            rows_out.append({
                "tile_id": "T{:03d}_{:03d}".format(ty, tx),
                "row0": r0, "col0": c0, "size_px": TILE_PX,
                "lat_min": round(lat_min, 4), "lat_max": round(lat_max, 4),
                "lon_min": round(lon_min, 4), "lon_max": round(lon_max, 4),
                "crater_centres": ncr,
                "crater_px": int(sub.sum()),
                "crater_frac": round(float(sub.mean()), 4),
            })
    with (OUT / "tiles.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    busy = [r for r in rows_out if r["crater_centres"] > 0]
    print("  tiles: {} total, {} contain crater centres".format(len(rows_out), len(busy)))
    print("  wrote {}".format(OUT / "tiles.csv"))
    print("")
    print("done; outputs in {}".format(OUT))


if __name__ == "__main__":
    main()
