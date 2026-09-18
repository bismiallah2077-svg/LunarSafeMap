#!/usr/bin/env python3
"""Download the LROC WAC mosaic for the study area from the USGS Moon WMS.

Source : USGS Astrogeology planetary maps WMS
         https://planetarymaps.usgs.gov/cgi-bin/mapserv?map=/maps/earth/moon_simp_cyl.map
Layer  : LROC_WAC  (LROC Wide Angle Camera global mosaic, ~100 m/px)

The service returns a GeoTIFF tagged with an *Earth* datum (EPSG:4326);
its coordinates are in fact selenographic lon/lat degrees. The preprocessing
step re-assigns a lunar sphere CRS (R = 1737.4 km).

Usage:
  python scripts/download_wac.py --bbox "353 8 359 13" --res 100
"""
import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WMS = "https://planetarymaps.usgs.gov/cgi-bin/mapserv"
MAP_FILE = "/maps/earth/moon_simp_cyl.map"
MOON_M_PER_DEG = 30320.0  # 2*pi*1737400 m / 360
UA = "LunarSafeMap/0.1 (undergraduate research; python-urllib)"


def build_url(params):
    """Keep slashes unescaped so the map= path is passed through verbatim."""
    query = urllib.parse.urlencode(params, safe="/")
    return WMS + "?" + query


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default="353 8 359 13",
                    help="lon_min lat_min lon_max lat_max (degrees E, N)")
    ap.add_argument("--res", type=float, default=100.0, help="target m/px")
    ap.add_argument("--layer", default="LROC_WAC")
    ap.add_argument("--out", default=None, help="output dir (default data/raw/wac)")
    args = ap.parse_args()

    lon_min, lat_min, lon_max, lat_max = (float(v) for v in args.bbox.split())
    width = int(round((lon_max - lon_min) * MOON_M_PER_DEG / args.res))
    height = int(round((lat_max - lat_min) * MOON_M_PER_DEG / args.res))

    repo = Path(__file__).resolve().parents[1]
    outdir = Path(args.out) if args.out else repo / "data" / "raw" / "wac"
    outdir.mkdir(parents=True, exist_ok=True)

    stem = (f"WAC_LROC_{lon_min:.0f}E_{lon_max:.0f}E_"
            f"{lat_min:.0f}N_{lat_max:.0f}N_{args.res:.0f}m")
    tif = outdir / f"{stem}.tif"

    params = {
        "map": MAP_FILE,
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": args.layer,
        "STYLES": "",
        "SRS": "EPSG:4326",
        "BBOX": f"{lon_min},{lat_min},{lon_max},{lat_max}",
        "WIDTH": width,
        "HEIGHT": height,
        "FORMAT": "image/tiff",
    }
    url = build_url(params)
    print("GET " + url)

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = resp.read()
    tif.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()

    meta = {
        "product_id": stem,
        "type": "lroc_wac_mosaic",
        "layer": args.layer,
        "instrument": "LROC WAC global mosaic (via USGS Moon WMS)",
        "wms_endpoint": WMS,
        "map_file": MAP_FILE,
        "source_url": url,
        "bbox_lonlat": [lon_min, lat_min, lon_max, lat_max],
        "size_px": [width, height],
        "target_resolution_m": args.res,
        "crs_note": ("returned as EPSG:4326-tagged GeoTIFF; coordinates are "
                     "selenographic lon/lat, re-assign lunar sphere R=1737.4 km"),
        "size_bytes": len(data),
        "sha256": sha,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (outdir / f"{stem}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"saved  {tif}")
    print(f"size   {width} x {height} px, {len(data)} bytes")
    print(f"sha256 {sha}")


if __name__ == "__main__":
    main()