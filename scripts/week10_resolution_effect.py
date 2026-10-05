#!/usr/bin/env python3
"""Week 10: does a coarser DEM overestimate the safe area? (hypothesis H1)

H1 says that a low-resolution DEM smooths local slope and relief, so a safety
assessment built on it should report *more* safe terrain than one built on
high-resolution data.

Testing that with two different DEMs is confounded: NAC and SLDEM differ not
only in resolution but also in vertical accuracy, datum and processing.  This
script isolates the resolution effect instead, by **aggregating one and the same
DEM** to 59, 118, 237, 474 and 948 m (factors 1, 2, 4, 8, 16) and recomputing
the whole assessment each time:

  * the grid cells nest exactly, so the comparison is paired on identical
    ground locations rather than on statistics of different footprints;
  * thresholds, weights, crater catalogue and window sizes are held fixed, so the
    only variable is the pixel size.

The independent check with the real NAC DEM is done separately (see the week-10
notes): only the 7 x 45 km NAC strip overlaps the study area, and it overlaps
none of the top candidate sites, so it is used to confirm the direction of the
effect rather than as the primary experiment.

Outputs: outputs/week10/resolution_effect.csv, resolution_effect.png

Usage
  python scripts/week10_resolution_effect.py --selftest
  python scripts/week10_resolution_effect.py --factors 1 2 4 8 16
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import week5_terrain_metrics as w5  # noqa: E402
import week7_suitability as w7  # noqa: E402
import week7_compare_literature as w7c  # noqa: E402

OUT = REPO / "outputs" / "week10"
DEM = REPO / "data" / "interim" / "week4" / "sldem_rimae_bode.tif"
CRATER_HAZARD = REPO / "outputs" / "week7" / "hazard_crater.tif"

SAFE_SLOPE, DANGER_SLOPE = 5.0, 15.0
SAFE_ROUGH, DANGER_ROUGH = 1.0, 5.0
CLASS_SAFE_EDGE = 0.33
MOON_M_PER_DEG = 30320.0


def assess(z, valid, px, factor, crater_native=None):
    """Run the whole assessment on the DEM block-averaged by `factor`."""
    eff = factor * px
    metrics, eff, good = w5.metrics_at_scale(z, valid, px, eff)
    slope = metrics["slope"]
    rough = metrics["roughness"]
    h_slope = w7.ramp(np.nan_to_num(slope), SAFE_SLOPE, DANGER_SLOPE)
    h_rough = w7.ramp(np.nan_to_num(rough), SAFE_ROUGH, DANGER_ROUGH)
    h_slope = np.where(good, h_slope, np.nan)
    h_rough = np.where(good, h_rough, np.nan)

    # terrain only (two factors, equal weights)
    s_terrain = np.where(good, 0.5 * (np.nan_to_num(h_slope) + np.nan_to_num(h_rough)),
                         np.nan)
    out = {"eff_m": eff, "factor": factor, "good": good,
           "slope": slope, "rough": rough,
           "safe_terrain": (s_terrain < CLASS_SAFE_EDGE) & good,
           # H1 in its original form is a statement about the *slope* criterion,
           # so keep that isolated as well
           "safe_slope_only": (h_slope < CLASS_SAFE_EDGE) & good}

    if crater_native is not None:
        # blocks of the coarse grid map exactly onto blocks of the native grid
        cr, _ = w5.block_mean(np.nan_to_num(crater_native, nan=0.0),
                              np.isfinite(crater_native), factor)
        cr = np.where(np.isfinite(cr), cr, 0.0)
        ny, nx = s_terrain.shape
        s_full = np.where(good, (np.nan_to_num(h_slope) + np.nan_to_num(h_rough)
                                 + cr[:ny, :nx]) / 3.0, np.nan)
        out["safe_full"] = (s_full < CLASS_SAFE_EDGE) & good
    return out


def summary(res):
    sl = res["slope"][res["good"]]
    rg = res["rough"][res["good"]]
    row = {"factor": res["factor"], "eff_m": round(res["eff_m"], 1),
           "slope_median_deg": round(float(np.nanmedian(sl)), 2),
           "slope_p95_deg": round(float(np.nanpercentile(sl, 95)), 2),
           "slope_ge_15_pct": round(100.0 * float(np.nansum(sl >= 15.0))
                                    / float(np.isfinite(sl).sum()), 2),
           "rough_median_m": round(float(np.nanmedian(rg)), 2),
           "rough_p95_m": round(float(np.nanpercentile(rg, 95)), 2),
           "safe_slope_only_pct": round(100.0 * float(res["safe_slope_only"].sum())
                                        / float(res["good"].sum()), 2),
           "safe_terrain_pct": round(100.0 * float(res["safe_terrain"].sum())
                                     / float(res["good"].sum()), 2)}
    if "safe_full" in res:
        row["safe_full_pct"] = round(100.0 * float(res["safe_full"].sum())
                                     / float(res["good"].sum()), 2)
    return row


def selftest():
    print("=== self test ===")
    fails = []

    def check(name, got, want, tol=1e-6):
        ok = abs(float(got) - float(want)) <= tol
        print("  {:58s} got {:10.4f}  want {:10.4f}  {}".format(
            name, got, want, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    # 1) block averaging a linear ramp preserves the gradient
    n, px = 256, 60.0
    ii, jj = np.mgrid[0:n, 0:n]
    grade = 0.01                       # 0.01 m per metre = 1 m per 100 m
    ramp = (grade * jj * px).astype("float32")
    valid = np.ones_like(ramp, dtype=bool)
    fine = assess(ramp, valid, px, 1)
    coarse = assess(ramp, valid, px, 8)
    want = np.degrees(np.arctan(grade))
    check("slope of a ramp at 60 m", float(np.nanmedian(fine["slope"])), want, 0.05)
    check("slope of the same ramp at 480 m", float(np.nanmedian(coarse["slope"])),
          want, 0.05)

    # 2) roughness is *destroyed* by coarsening - the core of H1
    # amplitude 10 m: the fine assessment must be UNSAFE (roughness above the
    # 5 m danger threshold) so that coarsening has something to change
    amp = 10.0
    checker = (amp * ((ii + jj) % 2)).astype("float32")
    f = assess(checker, valid, px, 1)
    c = assess(checker, valid, px, 8)
    # in a 3x3 window of a 0/amp checkerboard the counts are 5:4, so the
    # population standard deviation is amp * sqrt(20) / 9
    check("roughness of a fine checkerboard", float(np.nanmedian(f["rough"])),
          amp * (20 ** 0.5) / 9.0, 0.2)
    check("roughness after 8x averaging", float(np.nanmedian(c["rough"])), 0.0, 0.6)
    check("the fine assessment calls the checkerboard unsafe",
          float(f["safe_terrain"].mean()), 0.0, 1e-9)
    check("the 8x averaged one is safe", float(c["safe_terrain"].mean()), 1.0, 1e-9)
    check("coarser DEM reports more safe terrain",
          float(c["safe_terrain"].mean()) - float(f["safe_terrain"].mean()) > 0,
          1.0)

    # 3) crater hazard blocks line up with the terrain blocks
    cr = np.ones((n, n), dtype="float32")
    with_cr = assess(ramp, valid, px, 4, crater_native=cr)
    check("full score with a crater layer of 1s",
          float(np.nanmean(with_cr["safe_full"])), 0.0, 1e-9)

    print("")
    print("RESULT:", "ALL CHECKS PASSED" if not fails else "FAILED -> " + ", ".join(fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--factors", nargs="+", type=int, default=[1, 2, 4, 8, 16])
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if args.selftest:
        return selftest()

    OUT.mkdir(parents=True, exist_ok=True)
    print("=== setup ===")
    z, valid, px = w5.read_dem(DEM)
    crater, _ = w7c.read_raster(CRATER_HAZARD)
    print("  DEM {} x {} at {:.2f} m/px".format(z.shape[1], z.shape[0], px))
    print("  thresholds: slope {:.0f}-{:.0f} deg, roughness {:.0f}-{:.0f} m, "
          "safe if S < {:.2f}".format(SAFE_SLOPE, DANGER_SLOPE, SAFE_ROUGH,
                                      DANGER_ROUGH, CLASS_SAFE_EDGE))

    results, rows = {}, []
    for f in args.factors:
        res = assess(z, valid, px, f, crater_native=crater)
        results[f] = res
        row = summary(res)
        rows.append(row)
        print("  factor {:>2} ({:>6.1f} m): slope p95 {:5.2f} deg | >=15 deg "
              "{:5.2f} % | rough p95 {:6.2f} m | safe: slope-only {:5.2f} %, "
              "slope+rough {:5.2f} %, +crater {:5.2f} %".format(
                  f, row["eff_m"], row["slope_p95_deg"], row["slope_ge_15_pct"],
                  row["rough_p95_m"], row["safe_slope_only_pct"],
                  row["safe_terrain_pct"], row.get("safe_full_pct", float("nan"))))

    # paired comparison on the coarsest grid: does coarsening make a cell safe
    # that the fine assessment called unsafe?
    finest, coarsest = args.factors[0], args.factors[-1]
    fin = results[finest]
    cfs = results[coarsest]
    ny = (z.shape[0] // coarsest) * coarsest
    nx = (z.shape[1] // coarsest) * coarsest
    flips = {}
    for key, label in (("safe_terrain", "slope + roughness"),
                       ("safe_slope_only", "slope criterion only")):
        f_safe = w5.block_mean(fin[key][:ny, :nx].astype("float64"),
                               fin["good"][:ny, :nx], coarsest)[0]
        c_safe = cfs[key][:f_safe.shape[0], :f_safe.shape[1]]
        both = np.isfinite(f_safe) & cfs["good"][:f_safe.shape[0], :f_safe.shape[1]]
        flips[label] = (float(np.nanmean((f_safe[both] < 0.5) & c_safe[both])),
                        float(np.nanmean((f_safe[both] > 0.5) & (~c_safe[both]))))
    print("")
    print("=== paired comparison on the {:.0f} m grid ({:,} cells) ===".format(
        coarsest * px, int(both.sum())))
    print("  cell flips between the {:.0f} m and {:.0f} m assessments:".format(
        px, coarsest * px))
    for label, (to_safe, to_unsafe) in flips.items():
        print("    {:<22} unsafe -> safe {:5.1f} %   safe -> unsafe {:5.1f} %".format(
            label, 100 * to_safe, 100 * to_unsafe))
    print("  area with only the slope criterion: fine {:.1f} % -> coarse {:.1f} %".format(
        100 * float(fin["safe_slope_only"][fin["good"]].mean()),
        100 * float(cfs["safe_slope_only"][cfs["good"]].mean())))
    for r in rows:
        r["flip_unsafe_to_safe_slope_pct"] = round(
            100 * flips["slope criterion only"][0], 2)
        r["flip_unsafe_to_safe_composite_pct"] = round(
            100 * flips["slope + roughness"][0], 2)

    with (OUT / "resolution_effect.csv").open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print("")
    print("  wrote resolution_effect.csv")

    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    xs = [r["eff_m"] for r in rows]
    ax[0][0].plot(xs, [r["safe_terrain_pct"] for r in rows], "o-",
                  label="terrain only (slope + roughness)")
    ax[0][0].plot(xs, [r["safe_slope_only_pct"] for r in rows], "^-",
                  label="slope criterion only")
    ax[0][0].plot(xs, [r.get("safe_full_pct", np.nan) for r in rows], "s--",
                  label="with the crater layer")
    ax[0][0].set_xlabel("effective pixel size (m)")
    ax[0][0].set_ylabel("safe area (%)")
    ax[0][0].set_title("effect of coarsening on the safe area")
    ax[0][0].legend()
    ax[0][0].grid(alpha=0.3)
    ax[0][1].plot(xs, [r["slope_p95_deg"] for r in rows], "o-", color="#c33")
    ax[0][1].set_xlabel("effective pixel size (m)")
    ax[0][1].set_ylabel("slope p95 (deg)")
    ax[0][1].set_title("steep terrain is averaged away")
    ax[0][1].grid(alpha=0.3)
    ax[1][0].plot(xs, [r["rough_median_m"] for r in rows], "o-", label="median")
    ax[1][0].plot(xs, [r["rough_p95_m"] for r in rows], "s-", label="p95")
    ax[1][0].set_xlabel("effective pixel size (m)")
    ax[1][0].set_ylabel("roughness (m)")
    ax[1][0].set_title("roughness collapses fastest")
    ax[1][0].legend()
    ax[1][0].grid(alpha=0.3)
    im = ax[1][1].imshow(fin["safe_terrain"], cmap="RdYlGn", vmin=0, vmax=1)
    ax[1][1].set_title("safe mask at {:.0f} m (green = safe)".format(fin["eff_m"]))
    ax[1][1].set_xticks([])
    ax[1][1].set_yticks([])
    fig.colorbar(im, ax=ax[1][1], fraction=0.046)
    fig.tight_layout()
    fig.savefig(OUT / "resolution_effect.png", dpi=140)
    print("  wrote resolution_effect.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
