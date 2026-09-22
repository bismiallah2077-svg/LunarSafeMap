#!/usr/bin/env python3
"""Search the LROC NAC archive for stereo-capable image pairs.

Two modes:

  offline  - analyse volume INDEX.TAB files already on disk
  fetch    - download the index of each LROC EDR volume first (needs network)

The LROC volume index is a CSV with 83 columns (see INDEX.LBL): product id,
orbit, slew angle, incidence/emission angles, corner coordinates, etc. Two
NAC images make a good stereo pair for DEM extraction when their convergence
angle towards the same ground point is roughly 15-30 degrees.

Examples
--------
  # analyse whatever indexes are cached
  python scripts/find_stereo_pairs.py --index-dir work/lroc_index \
      --region "353 8 359 13"

  # download the index of a specific volume, then analyse
  python scripts/find_stereo_pairs.py --fetch --volumes LROLRC_0051B \
      --index-dir work/lroc_index --region "353 8 359 13"

Proxy: honours http_proxy / https_proxy.
"""
import argparse
import csv
import glob
import math
import os
import urllib.request
from itertools import combinations

BASE = "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0"
R_MOON = 1737.4
UA = "LunarSafeMap/0.1 (undergraduate research)"

COLS = {
    1: "volume", 2: "path", 6: "product_id", 9: "orbit", 10: "slew",
    15: "start_time", 27: "frame", 58: "resolution", 59: "emission",
    60: "incidence", 66: "sc_lat", 67: "sc_lon", 70: "c_lat", 71: "c_lon",
    72: "ur_lat", 73: "ur_lon", 74: "lr_lat", 75: "lr_lon",
    76: "ll_lat", 77: "ll_lon", 78: "ul_lat", 79: "ul_lon", 81: "tcd",
}
STR = {"volume", "path", "product_id", "start_time", "frame"}


def fetch_index(volume, index_dir):
    os.makedirs(index_dir, exist_ok=True)
    dest = os.path.join(index_dir, f"{volume}_INDEX.TAB")
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        print(f"  {volume}: cached")
        return dest
    url = f"{BASE}/{volume}/INDEX/INDEX.TAB"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        f.write(r.read())
    print(f"  {volume}: {os.path.getsize(dest):,} bytes")
    return dest


def is_nac(pid):
    return len(pid) > 3 and pid[-2] in "LR" and pid[-1] in "EC"


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for raw in csv.reader(f):
            if len(raw) < 83:
                continue
            rec, ok = {}, True
            for n, name in COLS.items():
                v = raw[n - 1].strip()
                if name in STR:
                    rec[name] = v
                else:
                    try:
                        rec[name] = float(v)
                    except ValueError:
                        ok = False
                        break
            if ok:
                rows.append(rec)
    return rows


def poly(r):
    return [(r["ul_lon"], r["ul_lat"]), (r["ur_lon"], r["ur_lat"]),
            (r["lr_lon"], r["lr_lat"]), (r["ll_lon"], r["ll_lat"])]


def bbox(p):
    """Longitude-aware bounding box.

    A strip that straddles the 0/360 meridian (e.g. corners at 359.9 and 0.1)
    would otherwise look 360 degrees wide and falsely overlap everything, so
    longitudes are unwrapped relative to the first corner.
    """
    ref = p[0][0]
    xs = [((q[0] - ref + 180.0) % 360.0) - 180.0 + ref for q in p]
    ys = [q[1] for q in p]
    return min(xs), min(ys), max(xs), max(ys)


def vec(lat, lon, r):
    la, lo = math.radians(lat), math.radians(lon)
    return (r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo),
            r * math.sin(la))


def convergence(a, b, lat, lon):
    t = vec(lat, lon, R_MOON)
    va = tuple(x - y for x, y in zip(t, vec(a["sc_lat"], a["sc_lon"], a["tcd"])))
    vb = tuple(x - y for x, y in zip(t, vec(b["sc_lat"], b["sc_lon"], b["tcd"])))
    na, nb = math.dist(va, (0, 0, 0)), math.dist(vb, (0, 0, 0))
    d = sum(x * y for x, y in zip(va, vb))
    return math.degrees(math.acos(max(-1.0, min(1.0, d / (na * nb)))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-dir", default="work/lroc_index")
    ap.add_argument("--region", default="353 8 359 13",
                    help="west south east north (degrees east / north)")
    ap.add_argument("--fetch", action="store_true", help="download indexes first")
    ap.add_argument("--volumes", nargs="*", default=[], help="volume ids to fetch")
    ap.add_argument("--min-conv", type=float, default=12.0)
    ap.add_argument("--max-conv", type=float, default=35.0)
    args = ap.parse_args()

    if args.fetch:
        if not args.volumes:
            raise SystemExit("--fetch needs --volumes")
        print("downloading volume indexes:")
        for v in args.volumes:
            fetch_index(v, args.index_dir)

    rows = []
    for path in sorted(glob.glob(os.path.join(args.index_dir, "*_INDEX.TAB"))):
        got = load(path)
        print(f"{os.path.basename(path):30s} {len(got):6d} rows")
        rows.extend(got)

    nac = [r for r in rows if is_nac(r["product_id"])]
    print(f"\nNAC rows: {len(nac)}")

    w, s, e, n = (float(x) for x in args.region.split())
    inside = []
    for r in nac:
        bx = bbox(poly(r))
        if bx[2] >= w and bx[0] <= e and bx[3] >= s and bx[1] <= n:
            inside.append(r)
    print(f"NAC images intersecting region W{w} S{s} E{e} N{n}: {len(inside)}")

    good = []
    for a, b in combinations(inside, 2):
        ba, bb = bbox(poly(a)), bbox(poly(b))
        ox = min(ba[2], bb[2]) - max(ba[0], bb[0])
        oy = min(ba[3], bb[3]) - max(ba[1], bb[1])
        if ox <= 0.05 or oy <= 0.05:
            continue
        clat = (max(ba[1], bb[1]) + min(ba[3], bb[3])) / 2
        clon = (max(ba[0], bb[0]) + min(ba[2], bb[2])) / 2
        conv = convergence(a, b, clat, clon)
        if not (args.min_conv <= conv <= args.max_conv):
            continue
        good.append((conv, ox, oy, clat, clon, a, b))

    print(f"\nstereo pairs with convergence {args.min_conv}-{args.max_conv} deg: {len(good)}")
    good.sort(key=lambda t: abs(t[0] - 22))
    for conv, ox, oy, clat, clon, a, b in good[:15]:
        print(f"\n  {a['product_id']}  orbit {a['orbit']:.0f}  slew {a['slew']:+.2f}  "
              f"{a['start_time'][:10]}  inc {a['incidence']:.0f}  res {a['resolution']:.2f}")
        print(f"  {b['product_id']}  orbit {b['orbit']:.0f}  slew {b['slew']:+.2f}  "
              f"{b['start_time'][:10]}  inc {b['incidence']:.0f}  res {b['resolution']:.2f}")
        print(f"    convergence {conv:.1f} deg, overlap {ox:.2f} x {oy:.2f} deg, "
              f"centre {clat:.2f}N {clon:.2f}E")


if __name__ == "__main__":
    main()