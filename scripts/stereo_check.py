#!/usr/bin/env python3
"""Check whether two LROC NAC products form a usable stereo pair.

Fetches the metadata page of each product and reports the geometry that
matters for stereo photogrammetry (ASP / ISIS):

  * convergence angle  - the angle between the two lines of sight to the same
    ground point; 15-30 deg is the sweet spot for DEM work
  * emission / incidence angles, slew angle, resolution, acquisition time
  * ground-track separation

Usage:
  python scripts/stereo_check.py M1406995626LE M123456789LE
  python scripts/stereo_check.py --dataset CDR M1406995626LC M123456789LC

Proxy: honours http_proxy / https_proxy.
"""
import argparse
import math
import re
import urllib.request

VIEW = "https://data.lroc.im-ldi.com/lroc/view_lroc"
DATASETS = {
    "EDR": "LRO-L-LROC-2-EDR-V1.0",
    "CDR": "LRO-L-LROC-3-CDR-V1.0",
}
R_MOON = 1737.4
UA = "LunarSafeMap/0.1 (undergraduate research)"


def fetch(product_id: str, dataset: str) -> dict:
    url = f"{VIEW}/{DATASETS[dataset]}/{product_id}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        html = r.read().decode("utf-8", errors="replace")
    fields = {}
    for label, value in re.findall(r"<td>(.*?)</th>\s*<td>(.*?)</td>", html, re.S):
        clean = lambda s: re.sub(r"<[^>]+>", "", s).strip()
        fields[clean(label)] = clean(value)
    fields["_url"] = url
    return fields


def num(fields, key):
    try:
        return float(fields[key])
    except (KeyError, ValueError):
        return float("nan")


def vec(lat, lon, r):
    la, lo = math.radians(lat), math.radians(lon)
    return (r * math.cos(la) * math.cos(lo),
            r * math.cos(la) * math.sin(lo),
            r * math.sin(la))


def angle(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (na * nb)))))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs=2, help="two LROC product ids")
    ap.add_argument("--dataset", default=None, choices=sorted(DATASETS),
                    help="override for both ids; default infers from the suffix")
    args = ap.parse_args()

    def ds_for(pid: str) -> str:
        if args.dataset:
            return args.dataset
        return "CDR" if pid.endswith("C") else "EDR"   # ...LE/RE = EDR, ...LC/RC = CDR

    a = fetch(args.ids[0], ds_for(args.ids[0]))
    b = fetch(args.ids[1], ds_for(args.ids[1]))

    print(f"{'':22s}{args.ids[0]:>18s}{args.ids[1]:>18s}")
    for key in ("Product", "Start time", "Orbit number", "Slew angle",
                "Emission angle", "Incidence angle", "Phase angle",
                "Center latitude", "Center longitude", "Resolution",
                "Nac frame", "Pds volume name"):
        print(f"{key:22s}{a.get(key, '-'):>18s}{b.get(key, '-'):>18s}")

    # convergence angle towards the ground point observed by image A
    lat, lon = num(a, "Center latitude"), num(a, "Center longitude")
    tgt = vec(lat, lon, R_MOON)
    va = tuple(p - q for p, q in zip(tgt, vec(num(a, "Sub spacecraft latitude"),
                                              num(a, "Sub spacecraft longitude"),
                                              num(a, "Target center distance"))))
    vb = tuple(p - q for p, q in zip(tgt, vec(num(b, "Sub spacecraft latitude"),
                                              num(b, "Sub spacecraft longitude"),
                                              num(b, "Target center distance"))))
    conv = angle(va, vb)

    dlat = num(a, "Center latitude") - num(b, "Center latitude")
    dlon = (num(a, "Center longitude") - num(b, "Center longitude") + 180) % 360 - 180
    sep_km = math.hypot(dlat, dlon) * 30.32

    print(f"\nconvergence angle : {conv:.2f} deg   (target 15-30)")
    print(f"centre separation : {sep_km:.1f} km")
    if conv < 5:
        print("VERDICT: NOT a stereo pair - nearly identical viewing geometry")
        print("         (typical when both files are the SAME acquisition at")
        print("          different processing levels, e.g. LE and LC)")
    elif conv < 15:
        print("VERDICT: weak stereo - usable only for low-precision heights")
    elif conv <= 30:
        print("VERDICT: good stereo pair for DEM extraction")
    else:
        print("VERDICT: convergence too large - matching will struggle")


if __name__ == "__main__":
    main()