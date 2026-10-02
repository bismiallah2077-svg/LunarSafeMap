#!/usr/bin/env python3
"""Week 8: Monte Carlo uncertainty of the landing-site ranking.

Week 7 produced one suitability map per parameter set.  The question week 8 has
to answer is different: **how much of the ranking survives when we stop
pretending the parameters are known?**

Perturbed in every draw:
  * factor weights      - the author's AHP vector, each weight x U(1-j, 1+j)
  * slope thresholds    - safe in {3, 5, 8} deg,   danger in {10, 15, 20} deg
  * roughness thresholds- safe in {0.5, 1, 2} m,   danger in {3, 5, 10} m
  * crater rim buffer   - {500, 1000, 2000} m
  * crater catalogue    - the 632-detection (precision) or 897-detection (recall)
                          version from the week-6 review

Kept fixed (week 8 does not re-train the model): the DEM, the terrain metrics,
the crater footprints, the 59.2 m grid, the 5 km site window.

Reported:
  * per site: rank percentile distribution, probability of staying in the top 10,
    probability of being classified safe;
  * study area: distribution of the safe fraction, and per-pixel probability of
    being called safe / danger (i.e. where the answer is parameter-sensitive).

Speed trick: the expensive part of the crater layer is the distance transform to
the crater rims.  It is computed once per catalogue and then *rescaled* for each
rim buffer, which is what makes 200 draws take minutes instead of hours.

Usage
  python scripts/week8_montecarlo.py --selftest
  python scripts/week8_montecarlo.py --n 200
  python scripts/week8_montecarlo.py --n 500 --jitter 0.5 --seed 1
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from osgeo import gdal  # noqa: E402
from scipy import ndimage  # noqa: E402

gdal.UseExceptions()

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week5_terrain_metrics as w5  # noqa: E402
import week7_suitability as w7  # noqa: E402
import week7_compare_literature as w7c  # noqa: E402
from week6_build_crater_labels import crater_disc_mask  # noqa: E402

OUT = REPO / "outputs" / "week8"
W7 = REPO / "outputs" / "week7"
DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
SITES_CSV = REPO / "configs" / "landing_sites.csv"
CATALOGUES = {
    "precision": REPO / "outputs" / "week6" / "craters_detected.geojson",           # 632
    "recall": REPO / "outputs" / "week6" / "craters_detected_md0.5.geojson",        # 897
}

SLOPE_SAFE = (3.0, 5.0, 8.0)
SLOPE_DANGER = (10.0, 15.0, 20.0)
ROUGH_SAFE = (0.5, 1.0, 2.0)
ROUGH_DANGER = (3.0, 5.0, 10.0)
RIM_BUFFER = (500.0, 1000.0, 2000.0)
SCALE_M = 60.0
SITE_KM = 5.0
CLASS_EDGES = (0.33, 0.66)
AHP_WEIGHTS = (0.5499, 0.2098, 0.2402)
MOON_M_PER_DEG = 30320.0


def load_pool_sites():
    """Union of the week-7 candidate sites (all variants) and the paper's LS1-4."""
    pool = []
    for tag in ("equal", "entropy", "calib50_95", "ahp"):
        path = W7 / "candidate_sites_{}.csv".format(tag)
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                pool.append({"label": "{}#{}".format(row.get("rank", "?"), tag),
                             "lon": float(row["lon"]), "lat": float(row["lat"]),
                             "source": tag})
    if SITES_CSV.exists():
        with SITES_CSV.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(r for r in f if not r.startswith("#")):
                if not row.get("lon"):
                    continue
                pool.append({"label": row["label"].strip(),
                             "lon": float(row["lon"]), "lat": float(row["lat"]),
                             "source": "paper"})
    # de-duplicate: two sites closer than 2.5 km are the same place
    keep = []
    for s in pool:
        if any(w7_centre_km(s, k) < 2.5 for k in keep):
            continue
        keep.append(s)
    return keep


def w7_centre_km(a, b):
    dlat = (b["lat"] - a["lat"]) * MOON_M_PER_DEG / 1000.0
    dlon = (b["lon"] - a["lon"]) * MOON_M_PER_DEG / 1000.0 * math.cos(
        math.radians(0.5 * (a["lat"] + b["lat"])))
    return math.hypot(dlat, dlon)


def sample_weights(rng, weights, scheme="dirichlet", jitter=0.3, concentration=15.0):
    """Perturb the weight vector.

    dirichlet : weights ~ Dirichlet(concentration * centre).  The mean is exactly
                the centre vector and every draw stays on the simplex.  This is
                the standard way to express "the weights are uncertain" in MCDA.
    jitter    : each weight x U(1-j, 1+j) then renormalised.  Simple, but note
                that renormalisation can push a *small* component well outside
                the nominal +/- j (with the AHP centre, roughness reached 1.57x),
                so the realised range has to be reported, not assumed.
    """
    centre = np.asarray(weights, dtype="float64")
    centre = centre / centre.sum()
    if scheme == "dirichlet":
        return rng.dirichlet(np.maximum(centre * concentration, 1e-6))
    w = centre * rng.uniform(1.0 - jitter, 1.0 + jitter, 3)
    w = np.clip(w, 0.0, None)
    return w / w.sum()


def sample_draw(rng, jitter, weights, scheme="dirichlet", concentration=15.0):
    """One Monte Carlo draw of every uncertain parameter."""
    return {
        "weights": sample_weights(rng, weights, scheme, jitter, concentration),
        "slope_safe": float(rng.choice(SLOPE_SAFE)),
        "slope_danger": float(rng.choice(SLOPE_DANGER)),
        "rough_safe": float(rng.choice(ROUGH_SAFE)),
        "rough_danger": float(rng.choice(ROUGH_DANGER)),
        "rim_buffer": float(rng.choice(RIM_BUFFER)),
        "catalogue": str(rng.choice(list(CATALOGUES))),
    }


def hazard_layers(draw, slope, rough, dist, discs, good):
    """Build the three hazard layers for one draw (cheap: only rescaling)."""
    h_slope = np.where(good, w7.ramp(np.nan_to_num(slope), draw["slope_safe"],
                                     draw["slope_danger"]), np.nan).astype("float32")
    h_rough = np.where(good, w7.ramp(np.nan_to_num(rough), draw["rough_safe"],
                                     draw["rough_danger"]), np.nan).astype("float32")
    d = dist[draw["catalogue"]]
    h_crater = np.clip(1.0 - d / draw["rim_buffer"], 0.0, 1.0)
    h_crater[discs[draw["catalogue"]]] = 1.0
    h_crater = np.where(good, h_crater, np.nan).astype("float32")
    return h_slope, h_rough, h_crater


def score_from(h_slope, h_rough, h_crater, w, good):
    acc = (w[0] * np.nan_to_num(h_slope) + w[1] * np.nan_to_num(h_rough)
           + w[2] * np.nan_to_num(h_crater))
    s = np.where(good, acc, np.nan).astype("float32")
    return s


def selftest():
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:58s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    rng = np.random.default_rng(0)
    centre = np.array(AHP_WEIGHTS) / np.sum(AHP_WEIGHTS)
    d = sample_draw(rng, 0.0, AHP_WEIGHTS, scheme="jitter")
    check("zero jitter returns the normalised centre", d["weights"][0], centre[0], 1e-9)
    check("weights still sum to one", float(d["weights"].sum()), 1.0)
    check("slope safe < danger", d["slope_safe"] < d["slope_danger"], 1.0)
    check("rough safe < danger", d["rough_safe"] < d["rough_danger"], 1.0)

    rng_a = np.random.default_rng(7)
    rng_b = np.random.default_rng(7)
    da = sample_draw(rng_a, 0.3, AHP_WEIGHTS)
    db = sample_draw(rng_b, 0.3, AHP_WEIGHTS)
    check("same seed -> same draw", da["weights"][1], db["weights"][1])
    check("draw picks a known catalogue", da["catalogue"] in CATALOGUES, 1.0)

    rng = np.random.default_rng(1)
    ws = np.array([sample_weights(rng, AHP_WEIGHTS, "dirichlet") for _ in range(4000)])
    check("dirichlet mean matches the centre (slope)", float(ws[:, 0].mean()),
          centre[0], 0.02)
    check("dirichlet mean matches the centre (crater)", float(ws[:, 2].mean()),
          centre[2], 0.02)
    check("dirichlet draws sum to one", float(np.abs(ws.sum(axis=1) - 1).max()), 0.0, 1e-9)
    check("dirichlet draws stay positive", float(ws.min() > 0), 1.0)
    check("dirichlet spread is finite and bounded",
          float(ws[:, 0].max() - ws[:, 0].min()) < 1.0, 1.0)

    # rank lookup: rank = 1 + number of strictly smaller windows
    field = np.array([[0.1, 0.2, 0.3, 0.4]], dtype="float32").ravel()
    srt = np.sort(field)
    check("rank of the smallest value", float(np.searchsorted(srt, 0.1, "left") + 1), 1.0)
    check("rank of the largest value", float(np.searchsorted(srt, 0.4, "left") + 1), 4.0)
    check("rank of a middle value", float(np.searchsorted(srt, 0.3, "left") + 1), 3.0)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--n", type=int, default=200, help="number of Monte Carlo draws")
    ap.add_argument("--jitter", type=float, default=0.3,
                    help="relative weight perturbation for --scheme jitter")
    ap.add_argument("--scheme", choices=("dirichlet", "jitter"), default="dirichlet",
                    help="weight sampling: dirichlet (default, mean = centre, stays "
                         "on the simplex) or jitter (multiplicative, renormalised)")
    ap.add_argument("--concentration", type=float, default=15.0,
                    help="Dirichlet concentration: larger = tighter around the centre")
    ap.add_argument("--weights", default=",".join(str(x) for x in AHP_WEIGHTS),
                    help="central weights (default: the author's AHP vector)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="",
                    help="suffix for the output files (use it when comparing "
                         "scenarios, otherwise a run overwrites the previous one)")
    ap.add_argument("--site-km", type=float, default=SITE_KM)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        return selftest()

    weights = np.array([float(t) for t in args.weights.split(",")])
    if weights.size != 3:
        raise SystemExit("--weights needs three comma separated numbers")
    weights = weights / weights.sum()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("=== setup ===")
    z, valid, px_m = w5.read_dem(DEM)
    ds = gdal.Open(str(DEM))
    gt, wkt = ds.GetGeoTransform(), ds.GetProjection()
    metrics, eff, good = w5.metrics_at_scale(z, valid, px_m, SCALE_M)
    slope, rough = metrics["slope"], metrics["roughness"]
    print("  DEM {} x {} at {:.2f} m/px, terrain support {:.0f} m".format(
        z.shape[1], z.shape[0], px_m, eff))

    dist, discs = {}, {}
    for name, path in CATALOGUES.items():
        craters = w7.read_catalogue(path)
        discs[name] = crater_disc_mask(z.shape, gt, craters).astype(bool)
        dist[name] = (ndimage.distance_transform_edt(~discs[name]) * px_m).astype("float32")
        print("  catalogue {:<9}: {:,} craters, disc coverage {:.2f} %".format(
            name, len(craters), 100.0 * discs[name].mean()))

    pool = load_pool_sites()
    px_rc = []
    for s in pool:
        r, c = w7c.to_pixel(gt, s["lon"], s["lat"])
        s["row"], s["col"] = int(r), int(c)
        px_rc.append((s["row"], s["col"]))
    print("  candidate pool: {:,} distinct sites (week-7 top sites + the paper's)".format(len(pool)))

    win = max(3, int(round(args.site_km * 1000.0 / px_m)))
    rng = np.random.default_rng(args.seed)
    n_valid = int(good.sum())
    safe_frac = np.zeros(args.n, dtype="float64")
    mean_s = np.zeros(args.n, dtype="float64")
    rank_pct = np.zeros((args.n, len(pool)), dtype="float32")
    safe_px = np.zeros(z.shape, dtype="uint16")
    danger_px = np.zeros(z.shape, dtype="uint16")
    draws = []

    print("")
    print("=== Monte Carlo: {} draws, weight scheme {}, seed {} ===".format(
        args.n, args.scheme, args.seed))
    if args.scheme == "dirichlet":
        print("  weights ~ Dirichlet({:.0f} x centre), centre = {}".format(
            args.concentration, ", ".join("{:.3f}".format(x) for x in weights)))
    else:
        print("  weights = centre x U({:.2f}, {:.2f}), renormalised".format(
            1 - args.jitter, 1 + args.jitter))
    for i in range(args.n):
        d = sample_draw(rng, args.jitter, weights, args.scheme, args.concentration)
        hs, hr, hc = hazard_layers(d, slope, rough, dist, discs, good)
        s = score_from(hs, hr, hc, d["weights"], good)
        cls = w7.classify(s, CLASS_EDGES)
        ok = np.isfinite(s)
        safe_px += ((cls == 1) & ok).astype("uint16")
        danger_px += ((cls == 3) & ok).astype("uint16")
        mean, _danger = w7.window_stats_field(s, cls, win)
        v = mean[np.isfinite(mean)]
        safe_frac[i] = float((v < CLASS_EDGES[0]).mean())
        mean_s[i] = float(np.nanmean(s))
        srt = np.sort(v)
        n_win = srt.size
        for k, (r, c) in enumerate(px_rc):
            x = mean[r, c]
            if not np.isfinite(x):
                rank_pct[i, k] = np.nan
                continue
            rk = int(np.searchsorted(srt, x, "left")) + 1
            rank_pct[i, k] = 100.0 * (n_win - rk) / n_win
        draws.append(d)
        if (i + 1) % max(1, args.n // 10) == 0:
            print("  {:4d}/{:4d}  ({:.0f} s, safe fraction so far {:.3f})".format(
                i + 1, args.n, time.time() - t0, float(safe_frac[:i + 1].mean())))

    print("")
    print("=== safe-area fraction across the draws ===")
    lo, hi = np.percentile(safe_frac, [5, 95])
    print("  mean {:.3f}, 5-95 % interval [{:.3f}, {:.3f}], min {:.3f}, max {:.3f}".format(
        safe_frac.mean(), lo, hi, safe_frac.min(), safe_frac.max()))
    print("  (deterministic references: equal 0.584 / entropy 0.756 / calib 0.784 / AHP 0.707)")

    rows = []
    for k, s in enumerate(pool):
        pct = rank_pct[:, k]
        pct = pct[np.isfinite(pct)]
        rows.append({
            "label": s["label"], "lon": s["lon"], "lat": s["lat"], "source": s["source"],
            "rank_pct_mean": round(float(pct.mean()), 1) if pct.size else "",
            "rank_pct_p05": round(float(np.percentile(pct, 5)), 1) if pct.size else "",
            "rank_pct_p95": round(float(np.percentile(pct, 95)), 1) if pct.size else "",
            "p_top10": round(float((pct >= 90).mean()), 3) if pct.size else "",
            # share of draws in which this window sits in the better half of the
            # scene (rank percentile >= 50) - a *rank* statement, not the pixel
            # classification of week 7
            "p_better_half": round(float((pct >= 50).mean()), 3) if pct.size else "",
        })
    rows.sort(key=lambda r: -(r["rank_pct_mean"] if r["rank_pct_mean"] != "" else -1))
    tag = ("_" + args.tag) if args.tag else ""
    with (OUT / ("mc_sites" + tag + ".csv")).open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print("")
    print("=== most stable sites (mean rank percentile, 5-95 % interval) ===")
    print("  {:<16} {:>9} {:>8} {:>8} {:>8} {:>7}".format(
        "site", "lon E", "mean", "p05", "p95", "P(top10)"))
    for r in rows[:12]:
        print("  {:<16} {:>9.4f} {:>8} {:>8} {:>8} {:>7}".format(
            r["label"], r["lon"], r["rank_pct_mean"], r["rank_pct_p05"],
            r["rank_pct_p95"], r["p_top10"]))

    # per-pixel probability of being called safe / danger
    w7.write_raster(OUT / ("mc_prob_safe" + tag + ".tif"),
                    safe_px.astype("float32") / args.n,
                    gt, wkt, nodata=-1.0)
    w7.write_raster(OUT / ("mc_prob_danger" + tag + ".tif"),
                    danger_px.astype("float32") / args.n,
                    gt, wkt, nodata=-1.0)
    print("")
    print("  wrote mc_prob_safe.tif / mc_prob_danger.tif "
          "(per-pixel probability over {} draws)".format(args.n))

    with (OUT / ("mc_draws" + tag + ".csv")).open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["draw", "w_slope", "w_roughness", "w_crater", "slope_safe",
                     "slope_danger", "rough_safe", "rough_danger", "rim_buffer",
                     "catalogue", "safe_fraction", "mean_S"])
        for i, d in enumerate(draws):
            wr.writerow([i, *["{:.5f}".format(x) for x in d["weights"]],
                         d["slope_safe"], d["slope_danger"], d["rough_safe"],
                         d["rough_danger"], d["rim_buffer"], d["catalogue"],
                         round(float(safe_frac[i]), 5), round(float(mean_s[i]), 5)])
    print("  wrote mc_draws{}.csv (every draw, so any figure can be reproduced)".format(tag))

    wmat = np.array([d["weights"] for d in draws])
    print("")
    print("=== realised weight ranges (report these in the paper) ===")
    for k, nm in enumerate(("slope", "roughness", "crater")):
        c = weights[k]
        print("  {:<10} centre {:.3f} | drawn {:.3f} .. {:.3f} "
              "({:.2f}x .. {:.2f}x centre)".format(
                  nm, c, wmat[:, k].min(), wmat[:, k].max(),
                  wmat[:, k].min() / c, wmat[:, k].max() / c))

    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    ax[0][0].hist(100 * safe_frac, bins=30, color="#3b6", alpha=0.85)
    ax[0][0].set_xlabel("safe area (% of the study area)")
    ax[0][0].set_ylabel("draws")
    ax[0][0].set_title("distribution of the safe fraction ({} draws)".format(args.n))
    top = rows[:12][::-1]
    ax[0][1].barh([r["label"] for r in top],
                  [r["rank_pct_mean"] for r in top], color="#36c", alpha=0.85)
    ax[0][1].errorbar([r["rank_pct_mean"] for r in top],
                      range(len(top)),
                      xerr=[[r["rank_pct_mean"] - r["rank_pct_p05"] for r in top],
                            [r["rank_pct_p95"] - r["rank_pct_mean"] for r in top]],
                      fmt="none", ecolor="k", lw=1)
    ax[0][1].set_xlabel("rank percentile (100 = safest window in the scene)")
    ax[0][1].set_title("candidate sites: mean and 5-95 % interval")
    im = ax[1][0].imshow(danger_px / args.n, cmap="inferno", vmin=0, vmax=1)
    ax[1][0].set_title("P(danger) per pixel")
    fig.colorbar(im, ax=ax[1][0], fraction=0.046)
    im = ax[1][1].imshow(safe_px / args.n, cmap="viridis", vmin=0, vmax=1)
    ax[1][1].set_title("P(safe) per pixel")
    fig.colorbar(im, ax=ax[1][1], fraction=0.046)
    for a in ax.ravel()[2:]:
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT / ("mc_summary" + tag + ".png"), dpi=140)
    print("  wrote mc_summary{}.png".format(tag))
    print("")
    print("  total {:.0f} s".format(time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
