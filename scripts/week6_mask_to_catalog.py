#!/usr/bin/env python3
"""Week 6.3/6.4: turn the predicted mask into a crater catalogue.

  1. connected component labelling of the predicted mask;
  2. per component: area, equivalent diameter, centroid -> lat/lon;
  3. size filter (equivalent diameter below MIN_DET_KM is dropped, which
     removes most of the spurious pixels a segmentation net leaves behind);
  4. match detections against the Robbins ground truth and compute detection
     level metrics, overall and per diameter bin;
  5. write a GeoJSON catalogue (points with a diameter property) plus CSVs.

Matching rule: a detection matches a ground truth crater when the distance
between their centres is smaller than MATCH_FRAC * the ground truth diameter
(default 0.5, i.e. the detection centre must fall inside the crater).
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal
from scipy import ndimage

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
W6 = REPO / "outputs" / "week6"
INTERIM = REPO / "data" / "interim" / "week6"
MASK = W6 / "study_area_crater_pred.tif"
GT = INTERIM / "craters_study_area.csv"

MOON_M_PER_DEG = 30320.0
R_MOON_KM = 1737.4
MIN_DET_KM = 1.0
MATCH_FRAC = 0.5
DIAM_BINS = [(1.0, 2.0), (2.0, 5.0), (5.0, 100.0)]


def load_mask(path=None):
    path = MASK if path is None else Path(path)
    ds = gdal.Open(str(path))
    if ds is None:
        raise SystemExit("cannot open {}".format(path))
    band = ds.GetRasterBand(1)
    m = (band.ReadAsArray() > 0).astype(np.uint8)
    return m, ds.GetGeoTransform(), ds


def components(mask, gt):
    """Connected components -> detections with lat/lon and equivalent diameter."""
    px_m = abs(gt[1]) * MOON_M_PER_DEG
    lab, n = ndimage.label(mask)
    if n == 0:
        return [], px_m
    area = np.bincount(lab.ravel())
    keep = [i for i in range(1, n + 1) if area[i] > 0]
    cent = ndimage.center_of_mass(mask, lab, keep)
    out = []
    for (rc, cc), i in zip(cent, keep):
        a = area[i]
        d_km = 2.0 * math.sqrt(a / math.pi) * px_m / 1000.0
        out.append({
            "lat": float(gt[3] + gt[5] * (rc + 0.5)),
            "lon": float(gt[0] + gt[1] * (cc + 0.5)),
            "diam_km": float(d_km),
            "area_px": int(a),
        })
    return out, px_m


def read_gt(path, min_diam=1.0, max_diam=100.0):
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                lat, lon, d = float(row["lat"]), float(row["lon"]), float(row["diameter_km"])
            except (KeyError, ValueError):
                continue
            if min_diam <= d <= max_diam:
                out.append({"lat": lat, "lon": lon, "diam_km": d})
    return out


def centre_distance_km(a, b):
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(b["lon"] - a["lon"])
    h = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * R_MOON_KM * math.asin(min(1.0, math.sqrt(h)))


def match(dets, gts, frac=MATCH_FRAC):
    """Greedy nearest-centre matching; returns (tp pairs, fp dets, fn gts)."""
    used = set()
    tp, fn = [], []
    for g in gts:
        best, best_d = None, 1e9
        for j, d in enumerate(dets):
            if j in used:
                continue
            dist = centre_distance_km(g, d)
            if dist < best_d:
                best, best_d = j, dist
        if best is not None and best_d < frac * g["diam_km"]:
            used.add(best)
            tp.append((g, dets[best], best_d))
        else:
            fn.append(g)
    fp = [d for j, d in enumerate(dets) if j not in used]
    return tp, fp, fn


def prf(tp, fp, fn):
    p = len(tp) / max(len(tp) + len(fp), 1)
    r = len(tp) / max(len(tp) + len(fn), 1)
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"n_det": len(tp) + len(fp), "n_tp": len(tp), "n_fp": len(fp),
            "n_fn": len(fn), "precision": round(p, 4), "recall": round(r, 4),
            "f1": round(f1, 4)}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser()
    ap.add_argument("--mask", default=str(MASK),
                    help="predicted mask to catalogue (default: the baseline run)")
    ap.add_argument("--tag", default="",
                    help="suffix for the output files, e.g. --tag dshade")
    args = ap.parse_args(argv)

    mask, gt, ds = load_mask(args.mask)
    print("=== predicted mask ===")
    print("  {}".format(args.mask))
    print("  grid {} x {}, coverage {:.2f} %".format(
        mask.shape[1], mask.shape[0], 100.0 * mask.mean()))
    dets_raw, px_m = components(mask, gt)
    dets = [d for d in dets_raw if d["diam_km"] >= MIN_DET_KM]
    print("  components: {:,} raw -> {:,} after the >= {:.1f} km filter".format(
        len(dets_raw), len(dets), MIN_DET_KM))
    gts = read_gt(GT)
    print("  ground truth (Robbins >= 1 km): {:,}".format(len(gts)))

    tp, fp, fn = match(dets, gts)
    overall = prf(tp, fp, fn)
    print("")
    print("=== detection level metrics (centre within {:.1f} x GT diameter) ===".format(MATCH_FRAC))
    print("  detected {:d} of {:d} known craters".format(overall["n_tp"], len(gts)))
    print("  precision {:.3f}   recall {:.3f}   F1 {:.3f}".format(
        overall["precision"], overall["recall"], overall["f1"]))
    print("  detections {} ({} correct, {} spurious)".format(
        overall["n_det"], overall["n_tp"], overall["n_fp"]))

    print("")
    print("=== per diameter bin ===")
    print("  {:>10s} {:>6s} {:>6s} {:>6s} {:>8s} {:>8s} {:>6s}".format(
        "diam (km)", "n_gt", "tp", "fp", "prec", "recall", "F1"))
    rows = []
    for lo, hi in DIAM_BINS:
        g_bin = [g for g in gts if lo <= g["diam_km"] < hi]
        if not g_bin:
            continue
        tp_b = [t for t in tp if lo <= t[0]["diam_km"] < hi]
        fn_b = [g for g in fn if lo <= g["diam_km"] < hi]
        fp_b = [d for d in fp if lo <= d["diam_km"] < hi]
        m = prf(tp_b, fp_b, fn_b)
        print("  {:>10s} {:6d} {:6d} {:6d} {:8.3f} {:8.3f} {:6.3f}".format(
            "{:.0f}-{:.0f}".format(lo, hi), len(g_bin), m["n_tp"], m["n_fp"],
            m["precision"], m["recall"], m["f1"]))
        rows.append({"bin_km": "{:.0f}-{:.0f}".format(lo, hi), "n_gt": len(g_bin), **m})

    suffix = ("_" + args.tag) if args.tag else ""
    metrics_csv = W6 / ("catalog_metrics" + suffix + ".csv")
    with metrics_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scope", "n_gt", "n_det", "n_tp", "n_fp", "n_fn",
                    "precision", "recall", "f1"])
        w.writerow(["all", len(gts), overall["n_det"], overall["n_tp"], overall["n_fp"],
                    overall["n_fn"], overall["precision"], overall["recall"], overall["f1"]])
        for r in rows:
            w.writerow([r["bin_km"], r["n_gt"], r["n_det"], r["n_tp"], r["n_fp"],
                        r["n_fn"], r["precision"], r["recall"], r["f1"]])
    print("")
    print("  wrote {}".format(metrics_csv))

    feats = []
    for d in dets:
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(d["lon"], 5), round(d["lat"], 5)]},
            "properties": {"diam_km": round(d["diam_km"], 3), "area_px": d["area_px"]},
        })
    gj = {"type": "FeatureCollection",
          "name": "RimaeBode_UNet_crater_catalogue",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
          "features": feats}
    geo_path = W6 / ("craters_detected" + suffix + ".geojson")
    with geo_path.open("w", encoding="utf-8") as f:
        json.dump(gj, f)
    print("  wrote {} ({} features)".format(geo_path, len(feats)))

    csv_path = W6 / ("craters_detected" + suffix + ".csv")
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["lat", "lon", "diam_km", "area_px"])
        w.writeheader()
        w.writerows(dets)
    print("  wrote {}".format(csv_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
