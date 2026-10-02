#!/usr/bin/env python3
"""Week 7.1-7.3: landing-site suitability from terrain, crater and hazard layers.

The suitability score is a weighted sum of normalised hazard layers

    S = w_slope * H_slope + w_rough * H_rough + w_crater * H_crater

where each H is a piecewise-linear ramp from 0 (safe) to 1 (unsafe) between a
"safe" and a "danger" threshold.  Everything is computed on the study-area
SLDEM grid (59.2 m/px, 353-359 E, 8-13 N).

Deliberate design choices (all of them are week-8 knobs):
  * thresholds, not z-scores: landing-site limits are engineering limits
    ("slope above 15 deg is unsafe"), so the ramp is defined on physical units;
  * equal weights by default.  Entropy weights are available (--weights entropy)
    but the whole point of week 8 is that the weights are not truth;
  * the crater layer is a *hazard*: 1 inside a mapped crater, decaying linearly
    to 0 at the rim plus a buffer.

Outputs (outputs/week7/): hazard_*.tif, suitability_<tag>.tif,
suitability_map.png, suitability_summary.csv, candidate_regions.{csv,geojson}

Usage
  python scripts/week7_suitability.py --selftest
  python scripts/week7_suitability.py                            # equal weights
  python scripts/week7_suitability.py --weights entropy
  python scripts/week7_suitability.py --weights 0.5,0.3,0.2 --tag w532
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from osgeo import gdal, ogr, osr  # noqa: E402
from scipy import ndimage  # noqa: E402

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week5_terrain_metrics as w5  # noqa: E402
from week6_build_crater_labels import crater_disc_mask  # noqa: E402

OUT = REPO / "outputs" / "week7"
STUDY_DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
DEFAULT_CATALOGUE = REPO / "outputs" / "week6" / "craters_detected.geojson"
SCALE_M = 60.0                # support of the terrain metrics (week 5 uses the same)

# physical limits: 0 below "safe", 1 above "danger"
SAFE_SLOPE, DANGER_SLOPE = 5.0, 15.0        # degrees
SAFE_ROUGH, DANGER_ROUGH = 1.0, 5.0         # metres, std in a 3x3 window
RIM_BUFFER_M = 1000.0                        # crater hazard decays over this distance
CLASS_EDGES = (0.33, 0.66)                   # safe / caution / danger


def ramp(x, safe, danger):
    """Piecewise-linear hazard: 0 at or below `safe`, 1 at or above `danger`."""
    if danger <= safe:
        raise ValueError("danger must exceed safe")
    return np.clip((x - safe) / (danger - safe), 0.0, 1.0)


def read_catalogue(path):
    """Read a week-6 GeoJSON catalogue -> [(lat, lon, diam_km), ...]."""
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    out = []
    for feat in gj["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        d = float(feat["properties"]["diam_km"])
        out.append((lat, lon, d))
    return out


def crater_hazard(shape, gt, craters, px_m, buffer_m=RIM_BUFFER_M):
    """1 inside a mapped crater, decaying linearly to 0 at rim + buffer."""
    if not craters:
        return np.zeros(shape, dtype="float32")
    discs = crater_disc_mask(shape, gt, craters).astype(bool)
    dist_px = ndimage.distance_transform_edt(~discs)     # 0 inside the disc
    dist_m = dist_px * px_m
    h = np.clip(1.0 - dist_m / buffer_m, 0.0, 1.0)
    h[discs] = 1.0
    return h.astype("float32")


def entropy_weights(layers, bins=256):
    """Entropy weighting of hazard layers (higher contrast -> higher weight)."""
    ws = []
    for a in layers:
        v = a[np.isfinite(a)]
        if v.size == 0 or float(v.max() - v.min()) <= 0:
            ws.append(0.0)
            continue
        h, _ = np.histogram(v, bins=bins, range=(0.0, 1.0))
        p = h.astype("float64")
        p = p[p > 0] / p.sum()
        e = -float((p * np.log(p)).sum()) / np.log(bins)
        ws.append(max(0.0, 1.0 - e))
    ws = np.asarray(ws, dtype="float64")
    if ws.sum() <= 0:
        ws = np.ones_like(ws)
    return ws / ws.sum()


def classify(score, edges=CLASS_EDGES):
    """1 = safe, 2 = caution, 3 = danger (0 = nodata)."""
    out = np.zeros(score.shape, dtype="uint8")
    ok = np.isfinite(score)
    out[ok] = 1
    out[ok & (score >= edges[0])] = 2
    out[ok & (score >= edges[1])] = 3
    return out


def window_stats_field(score, classes, win, min_valid=0.9):
    """Mean suitability and danger fraction inside a win x win window.

    Shared by the candidate-site ranking and by the comparison against the
    sites proposed in the literature, so both use exactly the same definition
    of "the suitability of a 5 km site".
    """
    ok = np.isfinite(score)
    cnt = ndimage.uniform_filter(ok.astype("float64"), size=win) * win ** 2
    s1 = ndimage.uniform_filter(np.where(ok, score, 0.0), size=win) * win ** 2
    enough = cnt >= min_valid * win ** 2
    mean = np.where(enough, s1 / np.maximum(cnt, 1e-9), np.nan)
    hazard = np.where(ok, (classes == 3).astype("float64"), 0.0)
    d1 = ndimage.uniform_filter(hazard, size=win) * win ** 2
    danger = np.where(enough, d1 / np.maximum(cnt, 1e-9), np.nan)
    return mean, danger


def rank_sites(score, classes, gt, px_m, site_km, top_n, min_valid=0.9):
    """Rank non-overlapping `site_km` x `site_km` windows by mean suitability.

    The largest contiguous "safe" region is thousands of km2 here, which is not
    a landing site.  A candidate site is a *local* choice, so the primitive is a
    sliding window: rank every valid window by its mean S, then take windows that
    do not overlap, best first.
    """
    win = max(3, int(round(site_km * 1000.0 / px_m)))
    mean, danger_frac = window_stats_field(score, classes, win, min_valid)

    order = np.argsort(np.where(np.isfinite(mean), mean, np.inf).ravel())
    taken = np.zeros(mean.shape, dtype=bool)
    sites = []
    for idx in order:
        r, c = divmod(int(idx), mean.shape[1])
        if not np.isfinite(mean[r, c]):
            break
        if taken[r, c]:
            continue
        lat = gt[3] + gt[5] * (r + 0.5)
        lon = gt[0] + gt[1] * (c + 0.5)
        sites.append({"lon": round(lon, 5), "lat": round(lat, 5),
                      "row": r, "col": c, "mean_S": round(float(mean[r, c]), 4),
                      "danger_pct": round(100 * max(0.0, float(danger_frac[r, c])), 2),
                      "site_km": site_km})
        r0, r1 = max(0, r - win), min(mean.shape[0], r + win + 1)
        c0, c1 = max(0, c - win), min(mean.shape[1], c + win + 1)
        taken[r0:r1, c0:c1] = True
        if len(sites) >= top_n:
            break
    return sites, win


def write_site_geojson(path, sites, gt):
    """Axis-aligned square polygons for the ranked candidate sites."""
    feats = []
    for i, s in enumerate(sites, 1):
        half_m = 0.5 * s["site_km"] * 1000.0
        dlat = half_m / 30320.0
        dlon = dlat / max(np.cos(np.radians(s["lat"])), 1e-6)
        lon, lat = s["lon"], s["lat"]
        ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat],
                [lon + dlon, lat + dlat], [lon - dlon, lat + dlat],
                [lon - dlon, lat - dlat]]
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"rank": i, "site_km": s["site_km"],
                                     "mean_S": s["mean_S"],
                                     "danger_pct": s["danger_pct"]}})
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection",
                   "name": "RimaeBode_candidate_sites", "features": feats}, f)
    return len(feats)


def nac_footprint(path):
    """Lon/lat bounds of a projected NAC DEM (0-360 longitude convention).

    The NAC DEM is in a lunar equirectangular projection ("SimpleCylindrical
    moon", R = 1737400 m, central meridian 354.81 E).  The parameters are read
    straight out of the WKT and the elementary conversion is done here: asking
    PROJ to transform to EPSG:4326 fails because the source is on the Moon and
    the target on the Earth ("Source and target ellipsoid do not belong to the
    same celestial body").
    """
    ds = gdal.Open(str(path))
    if ds is None:
        return None
    gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
    m = re.search(r'PARAMETER\["central_meridian",([0-9.\-]+)\]', wkt)
    lon0 = float(m.group(1)) if m else 0.0
    m = re.search(r'SPHEROID\["[^"]+",([0-9.]+)', wkt)
    radius = float(m.group(1)) if m else 1737400.0
    m_per_deg = math.pi * radius / 180.0
    xs = (gt[0], gt[0] + gt[1] * ds.RasterXSize)
    ys = (gt[3], gt[3] + gt[5] * ds.RasterYSize)
    lons = [((lon0 + x / m_per_deg) % 360.0) for x in xs]
    lats = [y / m_per_deg for y in ys]
    return min(lons), min(lats), max(lons), max(lats)


def write_raster(path, arr, gt, wkt, dtype="float32", nodata=-9999.0):
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(path), arr.shape[1], arr.shape[0], 1,
                    gdal.GDT_Float32 if dtype == "float32" else gdal.GDT_Byte)
    ds.SetGeoTransform(gt)
    ds.SetProjection(wkt)
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(np.where(np.isfinite(arr), arr, nodata).astype(dtype))
    band.FlushCache()
    ds = None


def find_candidates(classes, gt, wkt, px_m, min_area_km2, top_n, score, tag="equal"):
    """Largest contiguous safe areas -> polygon GeoJSON + CSV, ranked by area."""
    safe = (classes == 1)
    lab, n = ndimage.label(safe, structure=np.ones((3, 3), dtype="uint8"))
    if n == 0:
        return [], []
    px_km2 = (px_m / 1000.0) ** 2
    counts = np.bincount(lab.ravel())
    areas = counts * px_km2
    area_sum = ndimage.sum(score, lab, index=np.arange(1, n + 1))
    rows = []
    for i in range(1, n + 1):
        if areas[i] < min_area_km2:
            continue
        mean_s = float(area_sum[i - 1] / counts[i]) if counts[i] else float("nan")
        rows.append({"region_id": i, "area_km2": round(float(areas[i]), 3),
                     "mean_S": round(mean_s, 4)})
    rows.sort(key=lambda r: (-r["area_km2"], r["mean_S"]))
    rows = rows[:top_n]
    keep = {r["region_id"] for r in rows}
    if not keep:
        return [], rows

    # only the kept regions survive -> nodata 0 gives Polygonize a mask
    kept = np.where(np.isin(lab, list(keep)), lab, 0).astype("int32")
    mem = "/vsimem/week7_labels.tif"
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(mem, kept.shape[1], kept.shape[0], 1, gdal.GDT_Int32)
    ds.SetGeoTransform(gt)
    ds.SetProjection(wkt)
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(0)
    band.WriteArray(kept)
    stats = {r["region_id"]: r for r in rows}
    path = OUT / "candidate_regions_{}.geojson".format(tag)
    if path.exists():
        os.remove(path)
    vds = ogr.GetDriverByName("GeoJSON").CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromWkt(wkt)
    layer = vds.CreateLayer("candidates", srs, ogr.wkbPolygon)
    for name, typ in (("region_id", ogr.OFTInteger), ("area_km2", ogr.OFTReal),
                      ("mean_S", ogr.OFTReal)):
        layer.CreateField(ogr.FieldDefn(name, typ))
    gdal.Polygonize(band, band.GetMaskBand(), layer, 0, [])
    layer.StartTransaction()
    for feat in layer:
        rid = feat.GetField("region_id")
        st = stats.get(rid)
        if st is None:
            layer.DeleteFeature(feat.GetFID())
        else:
            feat.SetField("area_km2", st["area_km2"])
            feat.SetField("mean_S", st["mean_S"])
            layer.SetFeature(feat)
    layer.CommitTransaction()
    vds = None
    drv.Delete(mem)
    return rows, rows


def selftest():
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:56s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    check("ramp at the safe end", float(ramp(np.array([3.0]), 5, 15)[0]), 0.0)
    check("ramp at the danger end", float(ramp(np.array([20.0]), 5, 15)[0]), 1.0)
    check("ramp midway", float(ramp(np.array([10.0]), 5, 15)[0]), 0.5)

    flat = np.zeros((8, 8), dtype="float32")
    check("crater hazard with no craters", float(crater_hazard((8, 8), (0, 1, 0, 8, 0, -1),
                                                              [], 60.0).max()), 0.0)

    w = entropy_weights([flat, flat + 1.0])
    check("all-constant layers fall back to equal weights", float(w[0]), 0.5)
    check("entropy weights normalised", float(w.sum()), 1.0)
    w2 = entropy_weights([flat, np.linspace(0, 1, 64).astype("float32").reshape(8, 8)])
    check("constant layer gets no weight", float(w2[0]), 0.0)

    s = 0.5 * flat + 0.5 * flat
    check("weighted sum of two zero layers", float(s.max()), 0.0)
    c = classify(np.array([[0.0, 0.5, 0.9]], dtype="float32"))
    check("class of a safe pixel", int(c[0, 0]), 1)
    check("class of a caution pixel", int(c[0, 1]), 2)
    check("class of a danger pixel", int(c[0, 2]), 3)

    # a synthetic 1 km crater on a 60 m grid, centred on pixel (30, 30)
    dx_deg = 60.0 / 30320.0
    n = 60
    gt = (0.0, dx_deg, 0.0, 0.02, 0.0, -dx_deg)
    lat_c = 0.02 - dx_deg * 30.5
    lon_c = dx_deg * 30.5
    h = crater_hazard((n, n), gt, [(lat_c, lon_c, 1.0)], 60.0)
    check("centre of the synthetic crater is a hazard", float(h[30, 30]), 1.0)
    # the decay is measured FROM THE RIM, so each pixel outward costs 60 m of
    # the 1 km buffer regardless of where the rim happens to fall
    check("outward decay = 60 m per pixel of the buffer",
          float(h[30, 40] - h[30, 45]), 5 * 60.0 / 1000.0, tol=0.01)
    check("half the buffer beyond the rim -> 0.5",
          float(h[30, 30 + 17]), 0.5, tol=0.10)
    check("beyond rim + buffer -> safe", float(h[0, 0]), 0.0)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dem", default=str(STUDY_DEM))
    ap.add_argument("--catalogue", default=str(DEFAULT_CATALOGUE))
    ap.add_argument("--weights", default="equal",
                    help="equal | entropy | three comma separated numbers")
    ap.add_argument("--slope-safe", type=float, default=SAFE_SLOPE)
    ap.add_argument("--slope-danger", type=float, default=DANGER_SLOPE)
    ap.add_argument("--rough-safe", type=float, default=SAFE_ROUGH)
    ap.add_argument("--rough-danger", type=float, default=DANGER_ROUGH)
    ap.add_argument("--calibrate", default="",
                    help="comma separated percentiles (e.g. 50,95): derive the "
                         "slope AND roughness thresholds from the scene instead of "
                         "using fixed engineering limits.  Roughness has no universal "
                         "engineering limit, so this is the honest default - but it "
                         "must be reported, and week 8 perturbs it.")
    ap.add_argument("--rim-buffer", type=float, default=RIM_BUFFER_M)
    ap.add_argument("--min-area-km2", type=float, default=10.0)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--site-km", type=float, default=5.0,
                    help="size of a candidate landing site window (km)")
    ap.add_argument("--sites", type=int, default=10,
                    help="how many non-overlapping candidate sites to rank")
    ap.add_argument("--tag", default="equal")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        return selftest()

    OUT.mkdir(parents=True, exist_ok=True)
    print("=== 7.1 hazard layers ===")
    z, valid, px_m = w5.read_dem(Path(args.dem))
    ds = gdal.Open(args.dem)
    gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
    print("  DEM {} x {}, {:.2f} m/px, {:.1f} % valid".format(
        z.shape[1], z.shape[0], px_m, 100.0 * valid.mean()))

    metrics, eff, good = w5.metrics_at_scale(z, valid, px_m, SCALE_M)
    slope = metrics["slope"]
    rough = metrics["roughness"]
    if args.calibrate:
        p_lo, p_hi = (float(t) for t in args.calibrate.split(","))
        sv = slope[np.isfinite(slope)]
        rv = rough[np.isfinite(rough)]
        args.slope_safe = float(np.percentile(sv, p_lo))
        args.slope_danger = float(np.percentile(sv, p_hi))
        args.rough_safe = float(np.percentile(rv, p_lo))
        args.rough_danger = float(np.percentile(rv, p_hi))
        print("  calibrated thresholds from percentiles {:.0f}/{:.0f}:".format(p_lo, p_hi))
        print("    slope  {:.2f} -> {:.2f} deg".format(args.slope_safe, args.slope_danger))
        print("    rough  {:.2f} -> {:.2f} m".format(args.rough_safe, args.rough_danger))
    h_slope = np.where(good, ramp(np.nan_to_num(slope), args.slope_safe,
                                  args.slope_danger), np.nan).astype("float32")
    h_rough = np.where(good, ramp(np.nan_to_num(rough), args.rough_safe,
                                  args.rough_danger), np.nan).astype("float32")
    craters = read_catalogue(Path(args.catalogue))
    h_crater = crater_hazard(z.shape, gt, craters, px_m, args.rim_buffer)
    h_crater = np.where(good, h_crater, np.nan).astype("float32")
    print("  support {:.0f} m | slope p50 {:.2f} deg | roughness p50 {:.2f} m".format(
        eff, float(np.nanmedian(slope)), float(np.nanmedian(rough))))
    print("  craters in the hazard layer: {:,}".format(len(craters)))
    for nm, h in (("slope", h_slope), ("roughness", h_rough), ("crater", h_crater)):
        v = h[np.isfinite(h)]
        print("  H_{:<9} mean {:.3f}  fraction >= 0.5: {:5.1f} %".format(
            nm, float(v.mean()), 100.0 * float((v >= 0.5).mean())))

    print("")
    print("=== 7.2 weights ===")
    layers = [h_slope, h_rough, h_crater]
    if args.weights == "equal":
        w = np.array([1.0, 1.0, 1.0]) / 3.0
    elif args.weights == "entropy":
        w = entropy_weights(layers)
    else:
        w = np.array([float(t) for t in args.weights.split(",")])
        if w.size != 3:
            raise SystemExit("--weights needs three comma separated numbers")
        w = w / w.sum()
    print("  slope {:.3f}  roughness {:.3f}  crater {:.3f}".format(*w))

    score = np.full(z.shape, np.nan, dtype="float32")
    acc = np.zeros(z.shape, dtype="float64")
    ok = np.isfinite(h_slope) & np.isfinite(h_rough) & np.isfinite(h_crater)
    for wi, h in zip(w, layers):
        acc += wi * np.nan_to_num(h)
    score[ok] = acc[ok].astype("float32")

    classes = classify(score)
    v = score[ok]
    print("")
    print("=== 7.3 suitability ({} weights) ===".format(args.tag))
    print("  S: mean {:.3f}, p50 {:.3f}, p90 {:.3f}".format(
        float(v.mean()), float(np.median(v)), float(np.percentile(v, 90))))
    total = int(ok.sum())
    names = {1: "safe", 2: "caution", 3: "danger"}
    frac = {}
    for c in (1, 2, 3):
        frac[c] = float(((classes == c) & ok).sum()) / max(total, 1)
        print("  {}: {:5.1f} %".format(names[c], 100 * frac[c]))

    write_raster(OUT / "hazard_slope.tif", h_slope, gt, wkt)
    write_raster(OUT / "hazard_roughness.tif", h_rough, gt, wkt)
    write_raster(OUT / "hazard_crater.tif", h_crater, gt, wkt)
    write_raster(OUT / "suitability_{}.tif".format(args.tag), score, gt, wkt)
    write_raster(OUT / "suitability_classes_{}.tif".format(args.tag),
                 classes.astype("float32"), gt, wkt, dtype="byte", nodata=0)
    print("  wrote hazard_*.tif, suitability_{0}.tif, suitability_classes_{0}.tif"
          .format(args.tag))

    regions, _ = find_candidates(classes, gt, wkt, px_m, args.min_area_km2,
                                 args.top, np.nan_to_num(score), args.tag)
    if regions:
        with (OUT / "candidate_regions_{}.csv".format(args.tag)).open("w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=["region_id", "area_km2", "mean_S"])
            wr.writeheader()
            wr.writerows(regions)
        print("  candidates >= {:.0f} km2: {:,} (top {} written to "
              "candidate_regions_{}.csv/.geojson)".format(
                  args.min_area_km2, len(regions), len(regions), args.tag))
        for r in regions[:5]:
            print("    region {:>5}  area {:8.2f} km2  mean S {:.3f}".format(
                r["region_id"], r["area_km2"], r["mean_S"]))
    else:
        print("  no contiguous safe area >= {:.0f} km2".format(args.min_area_km2))

    sites, win_px = rank_sites(score, classes, gt, px_m, args.site_km, args.sites)
    if sites:
        nac = nac_footprint(REPO / "outputs" / "week4" / "nac_dem.tif")
        if nac:
            lo_lon, lo_lat, hi_lon, hi_lat = nac
            for s in sites:
                s["inside_nac"] = int(lo_lon <= s["lon"] <= hi_lon
                                      and lo_lat <= s["lat"] <= hi_lat)
            print("")
            print("  NAC strip (3.28 m/px) covers lon {:.3f}-{:.3f} E, lat {:.3f}-{:.3f} N"
                  .format(lo_lon, hi_lon, lo_lat, hi_lat))
            n_in = sum(s["inside_nac"] for s in sites)
            print("  candidate sites inside that strip: {:,} of {:,} "
                  "(only those can be checked against a metre-scale DEM)".format(
                      n_in, len(sites)))
        with (OUT / "candidate_sites_{}.csv".format(args.tag)).open("w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=["rank", "lon", "lat", "mean_S",
                                               "danger_pct", "site_km", "inside_nac"])
            wr.writeheader()
            for i, s in enumerate(sites, 1):
                wr.writerow({"rank": i, "lon": s["lon"], "lat": s["lat"],
                             "mean_S": s["mean_S"], "danger_pct": s["danger_pct"],
                             "site_km": s["site_km"],
                             "inside_nac": s.get("inside_nac", "")})
        n_poly = write_site_geojson(OUT / "candidate_sites_{}.geojson".format(args.tag),
                                    sites, gt)
        print("")
        print("=== candidate sites ({:.0f} km windows, {} px) ===".format(
            args.site_km, win_px))
        print("  {:>4} {:>10} {:>10} {:>8} {:>10}".format(
            "rank", "lon E", "lat N", "mean S", "danger % NAC"))
        for i, s in enumerate(sites, 1):
            print("  {:>4} {:>10.4f} {:>10.4f} {:>8.3f} {:>10.2f} {:>4}".format(
                i, s["lon"], s["lat"], s["mean_S"], s["danger_pct"],
                s.get("inside_nac", "-")))
        print("  wrote candidate_sites_{0}.csv and candidate_sites_{0}.geojson "
              "({1} polygons)".format(args.tag, n_poly))

    summary_path = OUT / "suitability_summary_{}.csv".format(args.tag)
    with summary_path.open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["tag", "w_slope", "w_roughness", "w_crater",
                     "slope_safe", "slope_danger", "rough_safe", "rough_danger",
                     "calibrate",
                     "rim_buffer_m", "n_craters", "valid_px", "S_mean", "S_p50",
                     "S_p90", "safe_pct", "caution_pct", "danger_pct", "n_candidates"])
        wr.writerow([args.tag, *["{:.4f}".format(x) for x in w],
                     args.slope_safe, args.slope_danger, args.rough_safe,
                     args.rough_danger, args.calibrate or "physical",
                     args.rim_buffer, len(craters), total,
                     round(float(v.mean()), 4), round(float(np.median(v)), 4),
                     round(float(np.percentile(v, 90)), 4),
                     round(100 * frac[1], 2), round(100 * frac[2], 2),
                     round(100 * frac[3], 2), len(regions)])
    print("  wrote {}".format(summary_path.name))

    fig, ax = plt.subplots(2, 3, figsize=(15, 8.5))
    for a, h, nm in zip(ax.ravel()[:3], layers, ("slope", "roughness", "crater")):
        im = a.imshow(h, cmap="inferno", vmin=0, vmax=1)
        a.set_title("hazard: {}".format(nm))
        fig.colorbar(im, ax=a, fraction=0.046)
    im = ax[1][0].imshow(score, cmap="RdYlGn_r", vmin=0, vmax=1)
    ax[1][0].set_title("suitability S ({} weights)".format(args.tag))
    fig.colorbar(im, ax=ax[1][0], fraction=0.046)
    if sites:
        rr = [s["row"] for s in sites]
        cc = [s["col"] for s in sites]
        for a in (ax[1][0], ax[1][1]):
            a.scatter(cc, rr, s=40, facecolors="none", edgecolors="cyan",
                      linewidths=1.4)
            for i, (r0, c0) in enumerate(zip(rr, cc), 1):
                a.annotate(str(i), (c0, r0), color="cyan", fontsize=8,
                           xytext=(4, -4), textcoords="offset points")
        ax[1][0].set_title("suitability S with the top {} sites".format(len(sites)))
    ax[1][1].imshow(classes, cmap="RdYlGn_r", vmin=1, vmax=3)
    ax[1][1].set_title("safe / caution / danger")
    ax[1][2].hist(v, bins=60, color="#444", alpha=0.85)
    for e in CLASS_EDGES:
        ax[1][2].axvline(e, color="red", ls="--", lw=1)
    ax[1][2].set_title("distribution of S")
    ax[1][2].set_xlabel("S")
    for a in ax.ravel():
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT / "suitability_map.png", dpi=140)
    print("  wrote suitability_map.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
